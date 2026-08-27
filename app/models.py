from typing import Optional, List
from pydantic import BaseModel, Field

class CreateGroupRequest(BaseModel):
    name: str = Field(..., min_length=1, description="Tên nhóm mới")

class ImportPagesRequest(BaseModel):
    pages_raw: str = Field(..., description="Danh sách link hoặc ID fanpage (mỗi dòng 1 page)")
    group_id: Optional[int] = None

class ImportCookiesRequest(BaseModel):
    cookies_raw: str = Field(..., description="Danh sách cookie tài khoản Facebook clone")
    name: Optional[str] = "Cookie Clone"

class UpdatePageGroupRequest(BaseModel):
    group_id: Optional[int] = None

class UpdateSettingsRequest(BaseModel):
    min_delay: float = Field(1.5, ge=0.1, le=30.0, description="Độ trễ tối thiểu giữa các page (giây)")
    max_delay: float = Field(3.5, ge=0.5, le=60.0, description="Độ trễ tối đa giữa các page (giây)")
    batch_size: int = Field(15, ge=1, le=100, description="Số page quét trước khi nghỉ xả hơi")
    rest_time: float = Field(8.0, ge=0.0, le=300.0, description="Thời gian nghỉ xả hơi (giây)")
    rotate_cookies: bool = Field(True, description="Tự động xoay vòng cookie")

class TriggerSyncRequest(BaseModel):
    group_id: Optional[int] = None
    force_all: bool = False
