import configparser
from os import environ

ENV_VAR = "MY_CONFIG"


class MyConfig:
    """Class to handle our configuration file.

    The configuration file name is defined in the environment variable
    <ENV_VAR>.

    Configuration file format:
    [SECTION]
    key = value

    Values can then be accessed as attributes of the class with the format
    section_key. Example:

    config = MyConfig()
    print(config.section_key)
    """

    def __init__(self) -> None:
        self._config = configparser.ConfigParser()

        if ENV_VAR not in environ:
            raise ValueError(f"Environment variable {ENV_VAR} not set")
        config_file = str(environ.get(ENV_VAR))
        self._config.read(config_file)
        self._attributes = {}

        for section in self._config.sections():
            for key, value in self._config.items(section):
                attr_name = f"{section.lower()}_{key}"
                self._attributes[attr_name] = value

    def __getattr__(self, name: str) -> str:
        if name in self._attributes:
            return self._attributes[name]
        raise AttributeError(
            f"'{self.__class__.__name__}' object has no attribute '{name}'"
        )
