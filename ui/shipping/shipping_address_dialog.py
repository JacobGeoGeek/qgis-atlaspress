from qgis.core import Qgis, QgsApplication, QgsMessageLog
from qgis.PyQt.QtWidgets import QDialog, QDialogButtonBox

from ...core.shipping.models import Country, ShippingAddress
from ...core.shipping.shipping_service import ShippingService
from ...core.shipping.tasks import FetchCountriesTask
from ..common.spinner_widget import SpinnerWidget
from .shipping_address_dialog_ui import Ui_AtlasPressShippingDialog


class ShippingAddressDialog(QDialog, Ui_AtlasPressShippingDialog):
    def __init__(
        self,
        shipping_service: ShippingService,
        on_shipping_address_completed: callable,
        on_back_requested: callable,
        parent=None,
    ):
        super().__init__(parent)
        self.setupUi(self)

        self._shipping_service = shipping_service
        self._on_shipping_address_completed = on_shipping_address_completed
        self._on_back_requested = on_back_requested
        self._countries: list[Country] = []
        self._current_address: ShippingAddress | None = None
        self._touched_fields: set[str] = set()
        self._show_all_errors = False

        self._spinner = SpinnerWidget()
        self.dialogLoadingSpinnerLabel.hide()
        self.dialogLoadingLayout.insertWidget(1, self._spinner)

        self._quote_button = self.buttonsActions.button(QDialogButtonBox.StandardButton.Ok)
        if self._quote_button is not None:
            self._quote_button.setText("Get Quote")
        self._back_button = self.buttonsActions.addButton(
            "Back",
            QDialogButtonBox.ButtonRole.ActionRole,
        )

        self.countryComboBox.setEditable(False)
        self.stateComboBox.setEditable(False)

        self._connect_signals()
        self._set_form_enabled(False)
        self._set_quote_enabled(False)
        self._load_countries()

    def _connect_signals(self) -> None:
        self.dialogRetryButton.clicked.connect(self._load_countries)
        self.buttonsActions.rejected.connect(self.reject)
        self.buttonsActions.accepted.disconnect(self.accept)
        self._back_button.clicked.connect(self._go_back)
        if self._quote_button is not None:
            self._quote_button.clicked.connect(self._submit)

        field_line_edits = {
            "name": self.nameLineEdit,
            "email": self.emailLineEdit,
            "address1": self.address1LineEdit,
            "address2": self.address2LineEdit,
            "city": self.cityLineEdit,
            "zip": self.postalLineEdit,
        }

        for field_name, line_edit in field_line_edits.items():
            line_edit.textEdited.connect(
                lambda _text, field=field_name: self._mark_field_touched(field)
            )
            line_edit.textChanged.connect(self._validate_form)

        self.countryComboBox.activated.connect(lambda _index: self._mark_field_touched("country"))
        self.stateComboBox.activated.connect(lambda _index: self._mark_field_touched("state"))
        self.countryComboBox.currentIndexChanged.connect(self._on_country_changed)
        self.stateComboBox.currentIndexChanged.connect(self._validate_form)

    def _load_countries(self) -> None:
        self._spinner.start()
        self._hide_all_errors()
        self._touched_fields.clear()
        self._show_all_errors = False
        self.dialogLoadingTextLabel.setText("Loading supported shipping countries...")
        self.dialogStackedWidget.setCurrentWidget(self.dialogLoadingPage)
        self.countryComboBox.clear()
        self.countryComboBox.addItem("Loading countries...", None)
        self.stateComboBox.clear()
        self.stateComboBox.addItem("Select a country first", None)
        self._set_form_enabled(False)
        self._set_quote_enabled(False)

        QgsApplication.taskManager().addTask(
            FetchCountriesTask(self._shipping_service, self._on_countries_loaded)
        )

    def _on_countries_loaded(self, result: bool, countries: list[Country]) -> None:
        self._spinner.stop()

        if not result:
            self.dialogErrorTitleLabel.setText("Could not load shipping countries")
            self.dialogErrorMessageLabel.setText("Please check your connection and try again.")
            self.dialogStackedWidget.setCurrentWidget(self.dialogErrorPage)
            return

        self._countries = sorted(countries, key=lambda country: country.name)
        self.countryComboBox.clear()
        self.countryComboBox.addItem("Select a country", None)

        for country in self._countries:
            self.countryComboBox.addItem(country.name, country)

        self.dialogStackedWidget.setCurrentWidget(self.dialogFormPage)
        self._set_form_enabled(True)
        self._on_country_changed()

    def _on_country_changed(self) -> None:
        country = self._selected_country()
        self.stateComboBox.clear()

        if country is None:
            self.stateComboBox.addItem("Select a country first", None)
            self._set_state_visible(False)
            self._validate_form()
            return

        if not country.states:
            self.stateComboBox.addItem("Not required", None)
            self._set_state_visible(False)
            self._validate_form()
            return

        self.stateComboBox.addItem("Select state/province", None)
        for state in sorted(country.states, key=lambda country_state: country_state.name):
            self.stateComboBox.addItem(state.name, state)

        self._set_state_visible(True)
        if "country" in self._touched_fields:
            self._touched_fields.add("state")
        self._validate_form()

    def _validate_form(self) -> None:
        country = self._selected_country()
        state = self.stateComboBox.currentData() if self.stateComboBox.isVisible() else None

        validation_result = self._shipping_service.validate_address(
            name=self.nameLineEdit.text(),
            email=self.emailLineEdit.text(),
            address1=self.address1LineEdit.text(),
            address2=self.address2LineEdit.text(),
            city=self.cityLineEdit.text(),
            state_code=state.code if state else None,
            country_code=country.code if country else "",
            zip_code=self.postalLineEdit.text(),
            countries=self._countries,
        )

        self._current_address = validation_result.address
        self._set_quote_enabled(validation_result.is_valid)
        self._show_validation_errors(validation_result.errors)

    def _submit(self) -> None:
        self._show_all_errors = True
        self._validate_form()

        if self._current_address is None:
            return

        QgsMessageLog.logMessage(
            "Shipping address captured and ready for quote generation.",
            "AtlasPress",
            level=Qgis.Info,
        )
        self._on_shipping_address_completed(self._current_address)
        self.accept()

    def _go_back(self) -> None:
        self.reject()
        self._on_back_requested()

    def _mark_field_touched(self, field_name: str) -> None:
        self._touched_fields.add(field_name)
        self._validate_form()

    def _selected_country(self) -> Country | None:
        country = self.countryComboBox.currentData()
        return country if isinstance(country, Country) else None

    def _show_validation_errors(self, errors: dict[str, str]) -> None:
        error_labels = {
            "name": self.nameErrorLabel,
            "email": self.emailErrorLabel,
            "address1": self.address1ErrorLabel,
            "city": self.cityErrorLabel,
            "country": self.countryErrorLabel,
            "state": self.stateErrorLabel,
            "zip": self.postalErrorLabel,
        }

        for field_name, label in error_labels.items():
            label.setText(errors.get(field_name, ""))
            label.setVisible(
                field_name in errors
                and (self._show_all_errors or field_name in self._touched_fields)
            )

    def _hide_all_errors(self) -> None:
        for label in [
            self.nameErrorLabel,
            self.emailErrorLabel,
            self.address1ErrorLabel,
            self.cityErrorLabel,
            self.countryErrorLabel,
            self.stateErrorLabel,
            self.postalErrorLabel,
        ]:
            label.clear()
            label.setVisible(False)

    def _set_state_visible(self, visible: bool) -> None:
        self.stateLabel.setVisible(visible)
        self.stateRequiredMark.setVisible(visible)
        self.stateComboBox.setVisible(visible)
        self.stateComboBox.setEnabled(visible)
        self.stateErrorLabel.setVisible(False)

    def _set_form_enabled(self, enabled: bool) -> None:
        for widget in [
            self.nameLineEdit,
            self.emailLineEdit,
            self.address1LineEdit,
            self.address2LineEdit,
            self.cityLineEdit,
            self.countryComboBox,
            self.postalLineEdit,
        ]:
            widget.setEnabled(enabled)

        self.stateComboBox.setEnabled(enabled and self.stateComboBox.isVisible())

    def _set_quote_enabled(self, enabled: bool) -> None:
        if self._quote_button is not None:
            self._quote_button.setEnabled(enabled)
