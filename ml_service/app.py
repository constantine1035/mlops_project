import os
import joblib
from datetime import datetime
from typing import List

import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    String,
    create_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker
from prometheus_fastapi_instrumentator import Instrumentator

try:
    from kafka import KafkaProducer
    import json
except ImportError:
    KafkaProducer = None


# Database configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+psycopg2://ml_user:ml_password@db:5432/ml_db"
)
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class Prediction(Base):
    __tablename__ = "predictions"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    # Features from the Wine dataset
    alcohol = Column(Float)
    malic_acid = Column(Float)
    ash = Column(Float)
    alcalinity_of_ash = Column(Float)
    magnesium = Column(Float)
    total_phenols = Column(Float)
    flavanoids = Column(Float)
    nonflavanoid_phenols = Column(Float)
    proanthocyanins = Column(Float)
    color_intensity = Column(Float)
    hue = Column(Float)
    od280_od315_of_diluted_wines = Column(Float)
    proline = Column(Float)
    prediction = Column(Integer)


# Create table if it doesn't exist
Base.metadata.create_all(bind=engine)


class WineFeatures(BaseModel):
    """Input schema matching the 13 chemical features of the Wine dataset."""

    alcohol: float
    malic_acid: float
    ash: float
    alcalinity_of_ash: float
    magnesium: float
    total_phenols: float
    flavanoids: float
    nonflavanoid_phenols: float
    proanthocyanins: float
    color_intensity: float
    hue: float
    od280_od315_of_diluted_wines: float
    proline: float

    class Config:
        schema_extra = {
            "example": {
                "alcohol": 13.0,
                "malic_acid": 2.0,
                "ash": 2.4,
                "alcalinity_of_ash": 15.0,
                "magnesium": 100.0,
                "total_phenols": 2.5,
                "flavanoids": 2.0,
                "nonflavanoid_phenols": 0.3,
                "proanthocyanins": 1.8,
                "color_intensity": 5.0,
                "hue": 1.0,
                "od280_od315_of_diluted_wines": 3.0,
                "proline": 1000.0,
            }
        }


class PredictionOut(BaseModel):
    id: int
    timestamp: datetime
    prediction: int

    class Config:
        orm_mode = True


# Load model and scaler; reload if file changed
MODEL_PATH = os.getenv("MODEL_PATH", "/app/model.joblib")
_model_data = None  # type: ignore
_model_mtime: float | None = None


def load_model():
    global _model_data, _model_mtime
    try:
        mtime = os.path.getmtime(MODEL_PATH)
    except OSError:
        raise RuntimeError(f"Model file not found at {MODEL_PATH}")
    if _model_data is None or _model_mtime != mtime:
        _model_data = joblib.load(MODEL_PATH)
        _model_mtime = mtime
    return _model_data


# Initialize Kafka producer if broker is available
def get_kafka_producer():
    if KafkaProducer is None:
        return None
    brokers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    try:
        producer = KafkaProducer(
            bootstrap_servers=brokers,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        )
        return producer
    except Exception:
        return None


producer = get_kafka_producer()

app = FastAPI(title="Wine Quality Classification Service")
Instrumentator().instrument(app).expose(app)


@app.post("/predict", response_model=PredictionOut)
def predict(features: WineFeatures):
    model_data = load_model()
    model = model_data["model"]
    scaler = model_data["scaler"]
    X = pd.DataFrame([features.dict()])
    X_scaled = scaler.transform(X)
    pred = int(model.predict(X_scaled)[0])
    # Save to database
    db = SessionLocal()
    record = Prediction(
        alcohol=features.alcohol,
        malic_acid=features.malic_acid,
        ash=features.ash,
        alcalinity_of_ash=features.alcalinity_of_ash,
        magnesium=features.magnesium,
        total_phenols=features.total_phenols,
        flavanoids=features.flavanoids,
        nonflavanoid_phenols=features.nonflavanoid_phenols,
        proanthocyanins=features.proanthocyanins,
        color_intensity=features.color_intensity,
        hue=features.hue,
        od280_od315_of_diluted_wines=features.od280_od315_of_diluted_wines,
        proline=features.proline,
        prediction=pred,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    db.close()
    # Send to Kafka topic if producer available
    if producer:
        try:
            producer.send(
                os.getenv("KAFKA_TOPIC", "predictions"),
                {
                    "timestamp": record.timestamp.isoformat(),
                    "prediction": pred,
                    "features": features.dict(),
                },
            )
            producer.flush()
        except Exception:
            pass
    return PredictionOut.from_orm(record)


@app.get("/history", response_model=List[PredictionOut])
def history(limit: int = 100):
    """Return the most recent predictions."""
    db = SessionLocal()
    records = (
        db.query(Prediction)
        .order_by(Prediction.timestamp.desc())
        .limit(limit)
        .all()
    )
    db.close()
    return [PredictionOut.from_orm(r) for r in records]