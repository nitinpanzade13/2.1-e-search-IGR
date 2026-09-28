from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.api.dependencies import get_db
from app.models.system import NetworkConfig
from app.schemas.system import NetworkConfigCreate, NetworkConfigUpdate, NetworkConfigResponse

router = APIRouter()

@router.get("/configs", response_model=List[NetworkConfigResponse])
def get_network_configs(db: Session = Depends(get_db)):
    return db.query(NetworkConfig).order_by(NetworkConfig.priority).all()

@router.post("/configs", response_model=NetworkConfigResponse)
def create_network_config(config: NetworkConfigCreate, db: Session = Depends(get_db)):
    db_config = db.query(NetworkConfig).filter(NetworkConfig.profile_name == config.profile_name).first()
    if db_config:
        raise HTTPException(status_code=400, detail="Profile name already registered")
        
    db_config = NetworkConfig(**config.model_dump())
    db.add(db_config)
    db.commit()
    db.refresh(db_config)
    return db_config

@router.put("/configs/{config_id}", response_model=NetworkConfigResponse)
def update_network_config(config_id: UUID, config: NetworkConfigUpdate, db: Session = Depends(get_db)):
    db_config = db.query(NetworkConfig).filter(NetworkConfig.id == config_id).first()
    if not db_config:
        raise HTTPException(status_code=404, detail="Network configuration not found")
        
    for key, value in config.model_dump(exclude_unset=True).items():
        setattr(db_config, key, value)
        
    db.commit()
    db.refresh(db_config)
    return db_config

@router.delete("/configs/{config_id}")
def delete_network_config(config_id: UUID, db: Session = Depends(get_db)):
    db_config = db.query(NetworkConfig).filter(NetworkConfig.id == config_id).first()
    if not db_config:
        raise HTTPException(status_code=404, detail="Network configuration not found")
        
    db.delete(db_config)
    db.commit()
    return {"ok": True}
