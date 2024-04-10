from pathlib import Path


class Properties:
    """Read Java's properties files and return a dictionary with the key-value pairs."""
    def __init__(self, path: Path) -> None:
        self.path = path
        self.properties = {}
        self.load()

    def load(self) -> None:
        with open(self.path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                key, value = line.split("=", 1)
                if value.lower() == "true":
                    value = True
                elif value.lower() == "false":
                    value = False
                if isinstance(value, str) and value.isdigit():
                    value = int(value)
                if isinstance(value, str):
                    self.properties[key.strip()] = value.strip()
                else:
                    self.properties[key.strip()] = value

    def save(self) -> None:
        with open(self.path, "w") as f:
            for key, value in self.properties.items():
                if value is True:
                    value = "true"
                elif value is False:
                    value = "false"
                f.write(f"{key}={value}\n")

    def __getitem__(self, key: str) -> str:
        return self.properties[key]

    def __setitem__(self, key: str, value: str) -> None:
        self.properties[key] = value

    def __delitem__(self, key: str) -> None:
        del self.properties[key]

    def __iter__(self):
        return iter(self.properties)

    def __len__(self) -> int:
        return len(self.properties)

    def __str__(self) -> str:
        return str(self.properties)
