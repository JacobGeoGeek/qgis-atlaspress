import re
from typing import Final

from .models import Country, ShippingAddress, ShippingValidationResult
from .shipping_repository import ShippingRepository

COUNTRIES_REQUIRING_STATE_CODE: Final[set[str]] = {"US", "CA", "AU"}
EMAIL_PATTERN: Final[re.Pattern] = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
US_ZIP_PATTERN: Final[re.Pattern] = re.compile(r"^\d{5}(-\d{4})?$")
CA_POSTAL_CODE_PATTERN: Final[re.Pattern] = re.compile(
    r"^[A-Z]\d[A-Z][ -]?\d[A-Z]\d$",
    re.IGNORECASE,
)


class ShippingService:
    def __init__(self, shipping_repository: ShippingRepository):
        self._shipping_repository = shipping_repository

    def get_countries(self) -> list[Country]:
        result = self._shipping_repository.get_countries()

        if result.error:
            raise Exception(f"Error fetching supported countries: {result.error.message}")

        return result.countries

    def validate_address(
        self,
        *,
        name: str,
        email: str,
        address1: str,
        address2: str,
        city: str,
        state_code: str | None,
        country_code: str,
        zip_code: str,
        countries: list[Country],
    ) -> ShippingValidationResult:
        normalized_name = name.strip()
        normalized_email = email.strip()
        normalized_address1 = address1.strip()
        normalized_address2 = address2.strip()
        normalized_city = city.strip()
        normalized_country_code = country_code.strip().upper()
        normalized_state_code = state_code.strip().upper() if state_code else None
        normalized_zip = zip_code.strip()

        if normalized_country_code == "CA":
            normalized_zip = normalized_zip.upper()

        errors: dict[str, str] = {}
        selected_country = self._find_country(normalized_country_code, countries)

        if not normalized_name:
            errors["name"] = "Recipient name is required."

        if not normalized_email:
            errors["email"] = "Email is required."
        elif not EMAIL_PATTERN.match(normalized_email):
            errors["email"] = "Enter a valid email address."

        if not normalized_address1:
            errors["address1"] = "Address line 1 is required."

        if not normalized_city:
            errors["city"] = "City is required."

        if not selected_country:
            errors["country"] = "Select a supported country."

        state_is_required = (
            normalized_country_code in COUNTRIES_REQUIRING_STATE_CODE
            or bool(selected_country and selected_country.states)
        )

        if state_is_required and not normalized_state_code:
            errors["state"] = "State/province is required for this country."
        elif normalized_state_code and selected_country and selected_country.states:
            valid_state_codes = {state.code for state in selected_country.states}
            if normalized_state_code not in valid_state_codes:
                errors["state"] = "Select a valid state/province."

        if not normalized_zip:
            errors["zip"] = "Postal/ZIP code is required."
        elif normalized_country_code == "US" and not US_ZIP_PATTERN.match(normalized_zip):
            errors["zip"] = "Enter a valid US ZIP code."
        elif normalized_country_code == "CA" and not CA_POSTAL_CODE_PATTERN.match(
            normalized_zip
        ):
            errors["zip"] = "Enter a valid Canadian postal code."

        if errors:
            return ShippingValidationResult(is_valid=False, address=None, errors=errors)

        address = ShippingAddress(
            name=normalized_name,
            email=normalized_email,
            address1=normalized_address1,
            address2=normalized_address2,
            city=normalized_city,
            state_code=normalized_state_code,
            country_code=normalized_country_code,
            zip=normalized_zip,
        )

        return ShippingValidationResult(is_valid=True, address=address, errors={})

    def _find_country(self, country_code: str, countries: list[Country]) -> Country | None:
        return next((country for country in countries if country.code == country_code), None)
