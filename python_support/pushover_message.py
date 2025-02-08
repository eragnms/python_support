"""Pushover message module.


This module contains the function to send a message to the Pushover server.
It can also be installed as a command line tool to send messages from the terminal.
Install with `pipx install .` and use with `pushover_message <message>`. In case of
running the script from the cli PUSHOVER_APP_TOKEN and PUSHOVER_USER_KEY environment
variables must be set.
"""

import http.client
import os
import sys
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


def main() -> None:
    # Read environment variables for app_token and user_key
    app_token = os.getenv("PUSHOVER_APP_TOKEN")
    user_key = os.getenv("PUSHOVER_USER_KEY")

    if not app_token or not user_key:
        print(
            "Error: PUSHOVER_APP_TOKEN or PUSHOVER_USER_KEY "
            "environment variables are not set."
        )
        sys.exit(1)

    # Ensure a message is passed as a CLI argument
    if len(sys.argv) < 2:
        print("Usage: pushover-message <message>")
        sys.exit(1)

    message = sys.argv[1]

    # Create PushoverMessage instance and send the message
    pushover = PushoverMessage(app_token, user_key)
    pushover.send(message)
    print("Pushover message sent successfully!")


if __name__ == "__main__":
    main()
