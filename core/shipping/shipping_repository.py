from typing import Final

from ..config.http_client import HttpClient
from ..config.model.http_response import HttpResponse, HttpResponseError
from .models import CountriesResponse, Country, CountryState


class ShippingRepository:
    def __init__(self, http_client: HttpClient):
        self._http_client = http_client

    def get_countries(self) -> CountriesResponse:
        response: Final[HttpResponse] = self._http_client.get(endpoint="/functions/v1/countries")

        if not response.is_success():
            error: Final[HttpResponseError] = HttpResponseError.from_response(response)
            return CountriesResponse(countries=[], error=error)

        data: Final[dict] = response.content_json() or {}
        countries_data: Final[list] = data.get("countries", [])
        countries: list[Country] = []

        for country_data in countries_data:
            country_code = str(country_data.get("code", "")).strip().upper()
            country_name = str(country_data.get("name", "")).strip()
            states = [
                CountryState(
                    code=str(state_data.get("code", "")).strip().upper(),
                    name=str(state_data.get("name", "")).strip(),
                )
                for state_data in country_data.get("states", [])
                if str(state_data.get("code", "")).strip()
                and str(state_data.get("name", "")).strip()
            ]

            countries.append(
                Country(
                    code=country_code,
                    name=country_name,
                    region=str(country_data.get("region", "")).strip(),
                    states=states,
                )
            )

        return CountriesResponse(countries=countries, error=None)
