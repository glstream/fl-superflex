import requests
from time import sleep
from requests.exceptions import RequestException


def make_api_call(
    url, params=None, headers=None, timeout=10, max_retries=3, backoff_factor=1
):
    for retry in range(max_retries):
        try:
            response = requests.get(
                url, params=params, headers=headers, timeout=timeout
            )
            response.raise_for_status()  # Raise an exception if the response contains an HTTP error status code
            return response.json()
        except RequestException as e:
            if retry < max_retries - 1:
                sleep_time = backoff_factor * (2 ** retry)
                print(
                    f"Error while making API call: {e}. Retrying in {sleep_time} seconds..."
                )
                sleep(sleep_time)
            else:
                print(
                    f"Error while making API call: {e}. Reached maximum retries ({max_retries})."
                )
                raise


def make_api_call_raw(
    url, params=None, headers=None, timeout=10, max_retries=3, backoff_factor=1
):
    for retry in range(max_retries):
        try:
            response = requests.get(
                url, params=params, headers=headers, timeout=timeout
            )
            response.raise_for_status()  # Raise an exception if the response contains an HTTP error status code
            return response
        except RequestException as e:
            if retry < max_retries - 1:
                sleep_time = backoff_factor * (2 ** retry)
                print(
                    f"Error while making API call: {e}. Retrying in {sleep_time} seconds..."
                )
                sleep(sleep_time)
            else:
                print(
                    f"Error while making API call: {e}. Reached maximum retries ({max_retries})."
                )
                raise
