FROM apache/airflow:2.6.3

USER airflow

COPY requirements_train.txt /tmp/requirements_train.txt
RUN pip install --no-cache-dir -r /tmp/requirements_train.txt

COPY airflow/dags /opt/airflow/dags
COPY train.py /opt/airflow/train.py
