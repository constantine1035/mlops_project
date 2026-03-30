# Wine Quality Classification Service

Беломестных Константин

## 1. Что за задача и зачем это нужно

### Бизнес-формулировка

У винодела есть партия вина на ранней стадии. Он уже померил химические показатели (кислотность, сахара, минералы), но ещё не прогнал всё через дегустационную комиссию.

Хочется:

- **быстро понять**, какие образцы выглядят перспективно;
- **не тратить лишние деньги** на дегустацию всего подряд;
- **копить историю** измерений и предсказаний, чтобы потом анализировать качество.

Этот сервис:

- принимает на вход 13 химических признаков;
- возвращает **бинарный прогноз**:  
  `1` — “интересный” (класс 2 в стандартном Wine Dataset),  
  `0` — всё остальное;
- сохраняет все предсказания в базу;
- отдаёт метрики, чтобы можно было смотреть на нагрузку и поведение сервиса.

Для бизнеса это выглядит как дешёвый фильтр “первой линии” перед более дорогой экспертизой.

---

## 2. Обзор архитектуры

Все компоненты крутятся внутри Docker и поднимаются через `docker compose up`.

**Компоненты:**

1. **ML-сервис (`ml_service`)**
2. **PostgreSQL (`db`)**
3. **Kafka + Zookeeper (`kafka`, `zookeeper`)**
4. **UI на Streamlit (`ui`)**
5. **Airflow-шедулер (`airflow`)**
6. **Prometheus (`prometheus`)**
7. **Grafana (`grafana`)**

Всё это связывается в одну систему через `docker-compose.yml`.

### Логический поток

1. Пользователь в UI вводит характеристики вина → нажимает “Predict”.
2. UI шлёт запрос в ML-сервис (FastAPI, `/predict`).
3. ML-сервис:
   - прогоняет данные через scaler и модель;
   - пишет запись в PostgreSQL (таблица `predictions`);
   - отправляет сообщение в Kafka (топик `predictions`);
   - обновляет метрики для Prometheus.
4. UI забирает историю предсказаний из БД и показывает её в таблице.
5. Prometheus периодически ходит на `/metrics` ML-сервиса и собирает метрики.
6. Grafana читает данные из Prometheus и рисует дашборды (например, скорость запросов).

Отдельно Airflow по расписанию запускает `train.py` и переобучает модель.

---

## 3. Компоненты по отдельности

### 3.1. ML-сервис (`ml_service`)

- Фреймворк: **FastAPI**
- Порт: `8000`
- Файл: `ml_service/app.py`
- Модель: логистическая регрессия из `scikit-learn` + `StandardScaler`
- Хранение артефактов: `model/model.joblib`

**Основные фичи:**

- эндпоинт `/predict`:
  - вход: JSON с 13 признаками:
    - `alcohol`
    - `malic_acid`
    - `ash`
    - `alcalinity_of_ash`
    - `magnesium`
    - `total_phenols`
    - `flavanoids`
    - `nonflavanoid_phenols`
    - `proanthocyanins`
    - `color_intensity`
    - `hue`
    - `od280_od315_of_diluted_wines`
    - `proline`
  - выход: `{"prediction": 0 или 1, "probability": float}`
- эндпоинт `/history` — подтягивает последние N предсказаний из PostgreSQL.
- эндпоинт `/metrics` — метрики для Prometheus.
- при старте грузит модель из `MODEL_PATH` (по умолчанию `model/model.joblib`).
- умеет публиковать сообщения в Kafka-топик `predictions`.

**База данных (PostgreSQL):**

Таблица `predictions` хранит:

- id, timestamp
- все 13 признаков
- `prediction` (0/1)
- `probability` (score модели)

Это позволяет потом делать аналитику и строить витрины.

---

### 3.2. PostgreSQL (`db`)

- Образ: `postgres:14`
- Порт: `5432`
- Данные хранятся в volume `db_data`.

Используется как:

- **онлайн-хранилище** для истории предсказаний, которое:
  - читает UI;
  - потенциально можно использовать для переобучения/аналитики.

---

### 3.3. Kafka + Zookeeper (`kafka`, `zookeeper`)

- Образы: `confluentinc/cp-zookeeper:5.5.7`, `confluentinc/cp-kafka:5.5.7`
- Порт Kafka: `9092`

ML-сервис публикует в Kafka сообщения вида:

```json
{
  "timestamp": "...",
  "features": { ... 13 признаков ... },
  "prediction": 0/1,
  "probability": 0.XXX
}
````

Сейчас в проекте нет отдельного консюмера, это заготовка под:

* стриминговый мониторинг,
* онлайн-обучение,
* real-time дашборды.

---

### 3.4. UI на Streamlit (`ui`)

* Фреймворк: **Streamlit**
* Порт: `8501`
* Файл: `ui/app.py`

Что умеет:

* форма для ввода всех 13 признаков (числовые поля с адекватными дефолтами);
* кнопка “Predict”:

  * посылает POST на `ml_service:8000/predict`;
  * показывает ответ модели;
* блок “History”:

  * тянет историю из `http://ml_service:8000/history`;
  * показывает последние предсказания в табличке.


---

### 3.5. Airflow (`airflow`)

* Образ: `apache/airflow:2.6.3`
* Порт: `8080`
* DAG-и лежат в `airflow/dags/`
* Скрипт обучения: `train.py` в корне

**DAG `model_retraining`:**

* запускается по расписанию (можно настроить в `train_dag.py`);

### Как руками дёрнуть DAG

1. Открываем `http://localhost:8080`.
2. Находим DAG `model_retraining`.
3. Включаем DAG и запускаем “Trigger DAG”.


---

### 3.6. Prometheus (`prometheus`) и Grafana (`grafana`)

**Prometheus:**

* порт: `9090`
* конфиг: `prometheus/prometheus.yml`
* собирает метрики с `ml_service:8000/metrics`

**Grafana:**

* порт: `3000`
* логин/пароль по умолчанию: `admin / admin`
* автоподключён datasource Prometheus (файл `grafana/provisioning/datasources/datasource.yml`)
* дашборд `Wine Quality Service Dashboard` (файл `grafana/provisioning/dashboards/wine_dashboard.json`)

Дашборд показывает, например:

* количество запросов к `/predict` во времени;
* можно легко добавить свои панели при желании.

---

## 4. Данные и модель

### Датасет

Используется стандартный Wine Dataset из `sklearn.datasets.load_wine()`:

* 13 признаков (химические характеристики),
* 3 исходных класса (3 сорта/категории вин).

Мы делаем из него бинарную задачу:

* `y = 1`, если исходный класс == 2,
* `y = 0` иначе.

Это просто честный и прозрачный способ получить бинарный таргет без танцев.

### Препроцессинг и модель

1. Загружаем данные `X, y`.
2. Делим на train/test.
3. Обучаем `StandardScaler` на train.
4. Обучаем `LogisticRegression` на скейленных данных.
5. Считаем accuracy на валидации.
6. Сохраняем:

   * `{"model": ..., "scaler": ...}` в `model/model.joblib`
   * метрику в `model/metrics.txt`

ML-сервис потом:

* загружает этот joblib;
* применяет scaler → модель;
* возвращает и логит, и probability.

---

## 5. Как это всё запустить

### Требования

* Docker и Docker Compose установлены;
* порты:

  * `8000` — API
  * `8501` — UI
  * `5432` — PostgreSQL
  * `9092` — Kafka
  * `9090` — Prometheus
  * `3000` — Grafana
  * `8080` — Airflow
    свободны.

### Шаги

1. Клонируем репозиторий:

   ```bash
   git clone <repo_url>
   cd mlops_project
   ```

2. (опционально) учим модель перед первым запуском:

   ```bash
   python train.py
   ```

   Это положит стартовую модель в `model/model.joblib`.

3. Поднять всё в Docker:

   ```bash
   docker compose up --build
   ```

4. Проверка:

   * API Swagger: `http://localhost:8000/docs`
   * UI: `http://localhost:8501`
   * Grafana: `http://localhost:3000`
   * Prometheus: `http://localhost:9090`
   * Airflow: `http://localhost:8080`

Остановить всё:

```bash
docker compose down
# или с подчисткой volume’ов:
docker compose down -v
```

---

## 6. Как пользоваться сервисом

### Вариант 1: через UI

1. Открываем `http://localhost:8501`.
2. Вводим значения признаков (по дефолту уже стоят адекватные или средние значения).
3. Жмем “Predict”.
4. Смотрим результат:

   * текстовый вывод (“модель считает, что это класс 2 / не класс 2”),
   * ниже — табличка с историей.

### Вариант 2: через API

Пример запроса:

```bash
curl -X POST "http://localhost:8000/predict" \
  -H "Content-Type: application/json" \
  -d '{
    "alcohol": 13.0,
    "malic_acid": 2.0,
    "ash": 2.3,
    "alcalinity_of_ash": 16.0,
    "magnesium": 100.0,
    "total_phenols": 2.0,
    "flavanoids": 2.5,
    "nonflavanoid_phenols": 0.3,
    "proanthocyanins": 1.8,
    "color_intensity": 5.0,
    "hue": 1.0,
    "od280_od315_of_diluted_wines": 3.0,
    "proline": 1000.0
  }'
```

Ответ будет примерно таким:

```json
{
  "prediction": 1,
  "probability": 0.87
}
```

История:

```bash
curl "http://localhost:8000/history?limit=20"
```

---

## 7. Мониторинг и метрики

### Prometheus

Метрики экспонируются на:

```text
http://localhost:8000/metrics
```

Prometheus сам их собирает (см. `prometheus/prometheus.yml`).

### Grafana

1. Идем на `http://localhost:3000`.
2. Логинимься (`admin / admin`).
3. Открываем дашборд `Wine Quality Service Dashboard`.

Там можно:

* смотреть количество запросов в секунду;
* расширять дашборд своими панелями (ошибки, latency и т.п., если добавить соответствующие метрики в FastAPI).

---

### One-pager

Для короткого саммари есть файл [`one_pager.md`](one_pager.md) — это краткое описание проекта