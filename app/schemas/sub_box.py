from pydantic import BaseModel, ConfigDict


class SubBoxBase(BaseModel):
    box_id: int
    position_identifier: str


class SubBoxCreate(SubBoxBase):
    pass


class SubBoxUpdate(BaseModel):
    pass


class SubBoxInDBBase(SubBoxBase):
    id: int
    readable_id: str

    model_config = ConfigDict(from_attributes=True)


class SubBox(SubBoxInDBBase):
    pass


class SubBoxInDB(SubBoxInDBBase):
    pass
