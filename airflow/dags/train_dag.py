"""
DAG для периодического переобучения модели. По расписанию запускается
скрипт train.py, который скачивает данные, обучает модель и сохраняет
файл model.joblib. Инференс-сервис автоматически подхватит новую
версию модели при выполнении следующих запросов.
"""

from datetime import datetime
from airflow import DAG
from airflow.operators.bash import BashOperator

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "start_date": datetime(2023, 1, 1),
    "retries": 0,
}

with DAG(
    dag_id="model_retraining",
    default_args=default_args,
    schedule_interval="@daily",
    catchup=False,
) as dag:
    retrain = BashOperator(
        task_id="retrain_model",
        bash_command="python /opt/airflow/train.py",
    )