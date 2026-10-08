import pandas as pd
import streamlit as st

st.set_page_config(page_title="Termómetro Financiero", page_icon="🌡️", layout="wide")


def plantilla_csv():
    df = pd.DataFrame({
        "Mes": ["Mes 1", "Mes 2", "Mes 3"],
        "Ingresos": [200, 1800, 2750],
        "Egresos": [2200, 2200, 2200],
    })
    return df.to_csv(index=False).encode("utf-8")


def leer_archivo(archivo):
    if archivo.name.lower().endswith(".csv"):
        df = pd.read_csv(archivo)
    else:
        df = pd.read_excel(archivo)
    df.columns = [str(c).strip().capitalize() for c in df.columns]
    faltan = [c for c in ["Mes", "Ingresos", "Egresos"] if c not in df.columns]
    if faltan:
        raise ValueError("Faltan estas columnas: " + ", ".join(faltan))
    df = df[["Mes", "Ingresos", "Egresos"]].copy()
    df["Ingresos"] = pd.to_numeric(df["Ingresos"], errors="coerce")
    df["Egresos"] = pd.to_numeric(df["Egresos"], errors="coerce")
    df = df.dropna()
    if df.empty:
        raise ValueError("No encontré filas con números válidos.")
    return df


def calcular(df, caja_inicial, factor_ingresos=1.0):
    d = df.copy()
    d["Ingresos"] = d["Ingresos"] * factor_ingresos
    d["Resultado"] = d["Ingresos"] - d["Egresos"]
    d["Caja"] = caja_inicial + d["Resultado"].cumsum()
    return d


def fmt(x, moneda):
    return f"{x:,.0f} {moneda}"


st.title("🌡️ Termómetro Financiero")
st.caption("Sube tus ingresos y egresos mensuales y obtén un diagnóstico al instante. "
           "Los datos no se guardan.")

with st.sidebar:
    st.header("Datos de partida")
    moneda = st.selectbox("Moneda", ["€", "CLP", "USD"])
    caja_inicial = st.number_input(f"Caja o financiación inicial ({moneda})",
                                   min_value=0.0, value=0.0, step=100.0)
    variacion = st.slider("Variación de ingresos para escenarios (%)", 5, 60, 30)
    st.download_button("⬇️ Descargar plantilla", plantilla_csv(),
                       file_name="plantilla_termometro.csv", mime="text/csv")

archivo = st.file_uploader("Sube tu archivo (Excel .xlsx o .csv)", type=["xlsx", "csv"])

if archivo is None:
    st.info("Descarga la plantilla en la barra lateral, llénala con tus cifras "
            "(una fila por mes) y súbela aquí.")
    st.stop()

try:
    datos = leer_archivo(archivo)
except Exception as e:
    st.error(f"No pude leer el archivo. {e}")
    st.stop()

base = calcular(datos, caja_inicial)
caja_final = base["Caja"].iloc[-1]
caja_minima = base["Caja"].min()
ultimo_resultado = base["Resultado"].iloc[-1]
equilibrio = base.loc[base["Resultado"] >= 0, "Mes"]
mes_equilibrio = equilibrio.iloc[0] if not equilibrio.empty else "No alcanzado"

if ultimo_resultado < 0 and caja_final > 0:
    autonomia = f"{caja_final / -ultimo_resultado:.1f} meses"
elif ultimo_resultado < 0:
    autonomia = "Sin caja"
else:
    autonomia = "No consume caja"

if caja_minima < 0:
    st.error("🔴 ROJO: en algún mes la caja queda en negativo. "
             "Con estos números hace falta más financiación o recortar gastos.")
elif ultimo_resultado < 0:
    st.warning("🟡 AMARILLO: la caja alcanza, pero el último mes sigue perdiendo dinero. "
               "Revisa cuánto tiempo te dura.")
else:
    st.success("🟢 VERDE: la caja no se agota y el último mes ya no pierde dinero.")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Caja final", fmt(caja_final, moneda))
c2.metric("Caja mínima", fmt(caja_minima, moneda))
c3.metric("Mes de equilibrio", mes_equilibrio)
c4.metric("Autonomía", autonomia)

st.subheader("Detalle mensual")
st.dataframe(base, width="stretch", hide_index=True)

st.subheader("Evolución")
st.line_chart(base.set_index("Mes")[["Ingresos", "Egresos", "Caja"]])

st.subheader(f"Escenarios (ingresos ±{variacion}%)")
filas = []
for nombre, factor in [("Pesimista", 1 - variacion / 100),
                       ("Base", 1.0),
                       ("Optimista", 1 + variacion / 100)]:
    e = calcular(datos, caja_inicial, factor)
    filas.append({
        "Escenario": nombre,
        "Caja final": round(e["Caja"].iloc[-1]),
        "Caja mínima": round(e["Caja"].min()),
        "Resultado último mes": round(e["Resultado"].iloc[-1]),
    })
st.dataframe(pd.DataFrame(filas), width="stretch", hide_index=True)


if __name__ == "__main__":
    main()
