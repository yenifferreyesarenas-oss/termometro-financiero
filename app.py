import re
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Termómetro Financiero", page_icon="🌡️", layout="wide")

DOCS = {33: "Factura", 34: "Factura exenta", 39: "Boleta", 41: "Boleta exenta",
        46: "Factura de compra", 56: "Nota de débito", 61: "Nota de crédito"}
DIAS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]


def num(df, col):
    if col not in df:
        return pd.Series(0.0, index=df.index)
    return pd.to_numeric(df[col], errors="coerce").fillna(0)


def leer(archivo):
    """Lee un archivo RCV del SII (compras, ventas con factura o boletas)."""
    nombre = archivo.name
    comp = "gzip" if nombre.lower().endswith(".gz") else None
    for enc in ("utf-8", "latin-1"):
        try:
            archivo.seek(0)
            df = pd.read_csv(archivo, sep=";", index_col=False, dtype=str,
                             compression=comp, encoding=enc)
            break
        except UnicodeDecodeError:
            continue
    df.columns = [c.strip() for c in df.columns]
    df = df.rename(columns={"Monto total": "Monto Total"})
    if "RUT Proveedor" in df:
        tipo, rut = "Compra", "RUT Proveedor"
    elif "Rut cliente" in df:
        tipo, rut = "Venta factura", "Rut cliente"
    elif "RUT Receptor" in df:
        tipo, rut = "Venta boleta", "RUT Receptor"
    else:
        raise ValueError(f"{nombre}: no reconozco el formato (¿es un archivo RCV del SII?)")
    df = df[pd.to_numeric(df.get("Tipo Doc"), errors="coerce").notna()].copy()
    out = pd.DataFrame(index=df.index)
    out["Tipo"] = tipo
    out["Doc"] = pd.to_numeric(df["Tipo Doc"]).astype(int)
    out["Fecha"] = pd.to_datetime(df["Fecha Docto"], dayfirst=True, errors="coerce")
    out["Contraparte"] = df[rut]
    out["Nombre"] = df["Razon Social"] if "Razon Social" in df else "Consumidores (boletas)"
    out["Folio"] = df["Folio"]
    signo = out["Doc"].eq(61).map({True: -1, False: 1})
    iva = num(df, "Monto IVA Recuperable") + num(df, "IVA Activo Fijo") if tipo == "Compra" \
        else num(df, "Monto IVA")
    out["Exento"] = num(df, "Monto Exento") * signo
    out["Neto"] = num(df, "Monto Neto") * signo
    out["IVA"] = iva * signo
    out["Total"] = num(df, "Monto Total") * signo
    out["Base"] = out["Exento"] + out["Neto"]
    m = re.search(r"_(20\d{4})", nombre)
    out["Periodo_RCV"] = f"{m.group(1)[:4]}-{m.group(1)[4:]}" if m else out["Fecha"].dt.strftime("%Y-%m")
    out["Periodo_Fecha"] = out["Fecha"].dt.strftime("%Y-%m")
    out["Documento"] = out["Doc"].map(DOCS).fillna(out["Doc"].astype(str))
    return out


def resumen_mensual(d, extra, ppm, caja0, c48=None):
    v = d[d["Tipo"].str.startswith("Venta")].groupby("Periodo")[["Base", "IVA"]].sum()
    if c48:
        s48 = pd.Series(c48, dtype=float)
        v = v.add(pd.DataFrame({"Base": s48, "IVA": (s48 * 0.19).round()}), fill_value=0)
    c = d[d["Tipo"] == "Compra"].groupby("Periodo")[["Base", "IVA"]].sum()
    m = pd.DataFrame({"Ventas netas": v["Base"], "Compras y gastos netos": c["Base"],
                      "IVA débito": v["IVA"], "IVA crédito": c["IVA"]}).fillna(0).sort_index()
    m["Gastos fuera del RCV"] = extra
    m["PPM"] = m["Ventas netas"] * ppm / 100
    m["Resultado"] = (m["Ventas netas"] - m["Compras y gastos netos"]
                      - m["Gastos fuera del RCV"] - m["PPM"])
    m["IVA a pagar"] = m["IVA débito"] - m["IVA crédito"]
    m["Caja estimada"] = caja0 + (m["Resultado"] - m["IVA a pagar"].clip(lower=0)).cumsum()
    return m


def clp(x):
    return f"${x:,.0f}".replace(",", ".")


# ----------------------------- INTERFAZ -----------------------------
st.title("🌡️ Termómetro Financiero")
st.caption("Sube los archivos RCV del SII (compras, ventas con factura y boletas). "
           "Los datos se procesan en tu sesión y no se guardan.")

with st.sidebar:
    st.header("Supuestos")
    caja0 = st.number_input("Caja inicial ($)", min_value=0.0, value=0.0, step=100000.0)
    v48 = st.number_input("Ventas con comprobante de pago electrónico, tipo 48 (neto mensual, $)",
                          min_value=0.0,
