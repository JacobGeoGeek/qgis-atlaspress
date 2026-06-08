from dataclasses import dataclass

from ...config.model.http_response import HttpResponseError


@dataclass(frozen=True)
class CountryState:
    code: str
    name: str


@dataclass(frozen=True)
class Country:
    code: str
    name: str
    region: str
    states: list[CountryState]


@dataclass(frozen=True)
class ShippingAddress:
    name: str
    email: str
    address1: str
    address2: str
    city: str
    state_code: str | None
    country_code: str
    zip: str

    def to_quote_recipient_payload(self) -> dict:
        payload = {
            "name": self.name,
            "email": self.email,
            "address1": self.address1,
            "city": self.city,
            "countryCode": self.country_code,
            "zip": self.zip,
        }

        if self.address2:
            payload["address2"] = self.address2

        if self.state_code:
            payload["stateCode"] = self.state_code

        return payload


@dataclass(frozen=True)
class CountriesResponse:
    countries: list[Country]
    error: HttpResponseError | None


@dataclass(frozen=True)
class ShippingValidationResult:
    is_valid: bool
    address: ShippingAddress | None
    errors: dict[str, str]
