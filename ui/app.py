import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="Wine Quality Predictor")
st.title("Wine Quality Predictor")

st.markdown(
    """
    Введите значения химических показателей вина, чтобы получить прогноз. 
    Модель определяет, будет ли качество вина высокое (1) или низкое (0).
    """
)

api_url = "http://ml_service:8000"

with st.form("prediction_form"):
    alcohol = st.number_input("Alcohol", value=13.0)
    malic_acid = st.number_input("Malic acid", value=2.0)
    ash = st.number_input("Ash", value=2.4)
    alcalinity_of_ash = st.number_input("Alcalinity of ash", value=15.0)
    magnesium = st.number_input("Magnesium", value=100.0)
    total_phenols = st.number_input("Total phenols", value=2.5)
    flavanoids = st.number_input("Flavanoids", value=2.0)
    nonflavanoid_phenols = st.number_input("Nonflavanoid phenols", value=0.3)
    proanthocyanins = st.number_input("Proanthocyanins", value=1.8)
    color_intensity = st.number_input("Color intensity", value=5.0)
    hue = st.number_input("Hue", value=1.0)
    od280_od315_of_diluted_wines = st.number_input("OD280/OD315 of diluted wines", value=3.0)
    proline = st.number_input("Proline", value=1000.0)
    submitted = st.form_submit_button("Predict")
    if submitted:
        payload = {
            "alcohol": alcohol,
            "malic_acid": malic_acid,
            "ash": ash,
            "alcalinity_of_ash": alcalinity_of_ash,
            "magnesium": magnesium,
            "total_phenols": total_phenols,
            "flavanoids": flavanoids,
            "nonflavanoid_phenols": nonflavanoid_phenols,
            "proanthocyanins": proanthocyanins,
            "color_intensity": color_intensity,
            "hue": hue,
            "od280_od315_of_diluted_wines": od280_od315_of_diluted_wines,
            "proline": proline,
        }
        try:
            resp = requests.post(f"{api_url}/predict", json=payload)
            resp.raise_for_status()
            result = resp.json()
            pred = result.get("prediction")
            st.success(
                f"Прогноз модели: {'класс 2 (положительный)' if pred == 1 else 'остальные классы'}"
            )
        except Exception as exc:
            st.error(f"Ошибка при запросе: {exc}")


st.subheader("История предсказаний")
try:
    resp = requests.get(f"{api_url}/history")
    resp.raise_for_status()
    history = resp.json()
    if history:
        df_hist = pd.DataFrame(history)
        df_hist["timestamp"] = pd.to_datetime(df_hist["timestamp"])
        st.dataframe(df_hist[["id", "timestamp", "prediction"]])
    else:
        st.info("История пуста")
except Exception as exc:
    st.error(f"Не удалось получить историю: {exc}")