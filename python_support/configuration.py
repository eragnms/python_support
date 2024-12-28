import configparser
from os import environ


class MyConfig:
    """Class to handle our configuration file.

    The configuration file name is defined in the environment variable
    <env_var>.

    Configuration file format:
    [SECTION]
    key = value

    Values can then be accessed as attributes of the class with the format
    section_key. Example:

    config = MyConfig()
    print(config.section_key)
    """

    def __init__(self, env_var: str) -> None:
        self._config = configparser.ConfigParser()

        if env_var not in environ:
            raise ValueError(f"Environment variable {env_var} not set")
        config_file = str(environ.get(env_var))
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
