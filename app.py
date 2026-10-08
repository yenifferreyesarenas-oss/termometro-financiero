import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

st.set_page_config(page_title="Termómetro Financiero | PFG & Agencia AIMA",
                   page_icon="🌡️", layout="wide")

FINANCIACION = 6600
TASA_CLP = 1073


def main():
    st.title("🌡️ Termómetro Financiero PFG & Agencia AIMA")
   
    st.markdown("---")

    df = pd.DataFrame({
        "Mes": ["Mes 1 (Instalación)", "Mes 2 (Arranque)", "Mes 3 (Consolidación)"],
        "Ingresos_EUR": [200, 1800, 2750],
        "Egresos_EUR": [2200, 2200, 2200],
    })
    df["Resultado_Mes"] = df["Ingresos_EUR"] - df["Egresos_EUR"]
    df["Resultado_Acumulado"] = df["Resultado_Mes"].cumsum()
    df["Saldo_Caja"] = FINANCIACION + df["Resultado_Acumulado"]
    df["Resultado_Acumulado_CLP"] = df["Resultado_Acumulado"] * TASA_CLP

    total_ingresos = df["Ingresos_EUR"].sum()
    total_egresos = df["Egresos_EUR"].sum()
    balance_final = total_ingresos - total_egresos
    caja_final = FINANCIACION + balance_final

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Financiación Inicial", f"{FINANCIACION:,.0f} €")
    c2.metric("Ingresos Proyectados (3M)", f"{total_ingresos:,.0f} €")
    c3.metric("Egresos Totales (3M)", f"{total_egresos:,.0f} €")
    c4.metric("Balance Operativo (3M)", f"{balance_final:,.0f} €")
    c5.metric("Caja Final", f"{caja_final:,.0f} €",
              delta=f"{caja_final - FINANCIACION:,.0f} € vs. inicial")

    st.markdown("---")
    st.subheader("📊 Estado de Resultados Mensual")
    st.dataframe(
        df[["Mes", "Ingresos_EUR", "Egresos_EUR", "Resultado_Mes",
            "Resultado_Acumulado", "Saldo_Caja"]],
        width="stretch", hide_index=True,
    )

    st.subheader("📈 Evolución de Ingresos vs. Egresos")
    fig, ax = plt.subplots(figsize=(8, 3.5))
    ax.plot(df["Mes"], df["Ingresos_EUR"], marker="o", label="Ingresos")
    ax.plot(df["Mes"], df["Egresos_EUR"], marker="o", label="Egresos")
    ax.plot(df["Mes"], df["Saldo_Caja"], marker="o", linestyle="--", label="Saldo de caja")
    ax.set_ylabel("EUR")
    ax.legend()
    ax.grid(alpha=0.3)
    st.pyplot(fig)

    with st.expander("Equivalente en CLP (1 € = 1.073 CLP)"):
        st.dataframe(df[["Mes", "Resultado_Acumulado_CLP"]],
                     width="stretch", hide_index=True)

  


if __name__ == "__main__":
    main()
