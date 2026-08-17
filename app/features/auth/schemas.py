from pydantic import BaseModel, ConfigDict, Field, field_validator


def _text(value: str) -> str:
    value = value.strip()
    if not value:
        msg = "Value cannot be empty."
        raise ValueError(msg)
    return value


def _password(value: str) -> str:
    if "\x00" in value:
        msg = "Password cannot contain NUL bytes."
        raise ValueError(msg)
    if len(value.encode()) > 72:
        msg = "Password cannot exceed 72 UTF-8 bytes."
        raise ValueError(msg)
    return value


class Credentials(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=False)
    username: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=1024)

    _validate_username = field_validator("username")(_text)
    _validate_password = field_validator("password")(_password)


class AccountPatch(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=False)
    current_password: str = Field(min_length=1, max_length=1024)
    username: str | None = Field(default=None, min_length=1, max_length=255)
    password: str | None = Field(default=None, min_length=1, max_length=1024)

    _validate_current = field_validator("current_password")(_password)
    _validate_username = field_validator("username")(_text)
    _validate_password = field_validator("password")(_password)


class ApiKeyCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=255)

    _validate_name = field_validator("name")(_text)
