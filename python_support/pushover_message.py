"""Pushover message module.


This module contains the function to send a message to the Pushover server.
"""

import http.client
import urllib.parse


class PushoverMessage:
    """
    Class to send a message to the Pushover server.

    Attributes:
        app_token: The Pushover application token.
        user_key: The Pushover user key.

    """

    def __init__(self, app_token: str, user_key: str) -> None:
        self._app_token = app_token
        self._user_key = user_key

    def send(self, message: str) -> None:
        """
        Send a message to the pushover server.
        """
        conn = http.client.HTTPSConnection("api.pushover.net:443")
        conn.request(
            "POST",
            "/1/messages.json",
            urllib.parse.urlencode(
                {
                    "token": self._app_token,
                    "user": self._user_key,
                    "message": message,
                }
            ),
            {"Content-type": "application/x-www-form-urlencoded"},
        )
        conn.getresponse()
