from typing import Annotated, Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db

SettingsDep= Annotated[Settings, Depends(get_settings)]
DBSession= Annotated[Session, Depends(get_db)]