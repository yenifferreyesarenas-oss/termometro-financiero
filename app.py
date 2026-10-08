import re
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Termómetro Financiero", page_icon="🌡️", layout="wide")

DOCS = {33: "Factura", 34: "Factura exenta", 39: "Boleta", 41: "Boleta exenta",
        46: "Factura de compra", 56: "Nota de débito", 61: "Nota de crédito"}
DIAS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]


def num(df, col):
    if col not in df:
        return pd.Series(0import re
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
    v48 = st.number_input("Ventas con comprobante de pago electrónico, tipo 48 (neto mensual, $)", min_value=0.0, value=0.0, step=100000.0, help="Ventas con tarjeta que no vienen en los CSV. Cópialas del resumen de ventas del SII, línea Comprobantes de Pago Electrónico (48), columna Monto Neto.")
    extra = st.number_input("Gastos mensuales fuera del RCV ($)", min_value=0.0, value=0.0,
                            step=50000.0,
                            help="Sueldos, honorarios, leasing, créditos u otros que no pasan por el RCV.")
    ppm = st.number_input("PPM (% sobre ventas netas)", min_value=0.0, value=0.25, step=0.05,
                          help="Confirma el porcentaje vigente con tu contador.")
    var = st.slider("Variación de ventas en escenarios (%)", 5, 60, 20)
    share = st.slider("% de las compras que sube/baja con las ventas", 0, 100, 70)
    base_per = st.radio("Agrupar por", ["Período tributario (nombre del archivo)", "Fecha del documento"])

archivos = st.file_uploader("Sube tus archivos RCV (.csv o .csv.gz), todos juntos",
                            type=["csv", "gz"], accept_multiple_files=True)
if not archivos:
    st.info("Sube los archivos de **compras**, **ventas (facturas)** y **boletas**. "
            "Puedes subir varios meses a la vez para ver la tendencia.")
    st.stop()

partes = []
for a in archivos:
    try:
        partes.append(leer(a))
    except Exception as e:
        st.error(f"No pude leer {a.name}. {e}")
if not partes:
    st.stop()

datos = pd.concat(partes, ignore_index=True)
datos["Periodo"] = datos["Periodo_RCV"] if base_per.startswith("Período") else datos["Periodo_Fecha"]
datos = datos.dropna(subset=["Periodo"])
ventas = datos[datos["Tipo"].str.startswith("Venta")]
compras = datos[datos["Tipo"] == "Compra"]
c48 = {p: v48 for p in datos["Periodo"].unique()}
m = resumen_mensual(datos, extra, ppm, caja0, c48)
tot = m.sum(numeric_only=True)
n = len(m)

if ventas.empty or compras.empty:
    st.warning("Falta algún tipo de archivo (ventas o compras): el resultado puede no ser representativo.")

margen = tot["Resultado"] / tot["Ventas netas"] if tot["Ventas netas"] else 0
res_mes = tot["Resultado"] / n
caja_fin = m["Caja estimada"].iloc[-1]
caja_min = m["Caja estimada"].min()
if res_mes < 0 and caja_fin > 0:
    autonomia = f"{caja_fin / -res_mes:.1f} meses"
elif res_mes < 0:
    autonomia = "Sin caja"
else:
    autonomia = "No consume caja"
brecha = max(0, -res_mes)

if caja_min < 0 or margen < 0:
    st.error("🔴 ROJO: el resultado del período es negativo. Los costos superan a las ventas.")
elif margen < 0.10:
    st.warning(f"🟡 AMARILLO: el margen es de {margen:.1%}, muy ajustado frente a imprevistos.")
else:
    st.success(f"🟢 VERDE: el período deja un margen de {margen:.1%} después de costos y PPM.")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Ventas netas", clp(tot["Ventas netas"]))
c2.metric("Compras y gastos netos", clp(tot["Compras y gastos netos"]))
c3.metric("Resultado", clp(tot["Resultado"]), delta=f"{margen:.1%} de margen")
c4.metric("IVA neto del período", clp(tot["IVA a pagar"]),
          help="Débito − crédito. Si es negativo, queda como remanente para el mes siguiente.")
c5, c6, c7, c8 = st.columns(4)
c5.metric("Caja estimada final", clp(caja_fin))
c6.metric("Autonomía", autonomia)
c7.metric("Venta mensual adicional para equilibrio", clp(brecha))
c8.metric("Documentos procesados", f"{len(datos):,}".replace(",", "."))

t1, t2, t3, t4, t5 = st.tabs(["Resumen", "Ventas", "Compras", "Escenarios", "Datos"])

with t1:
    st.subheader("Estado de resultados por período")
    st.dataframe(m.round(0).style.format("{:,.0f}"), width="stretch")
    st.subheader("Evolución")
    st.bar_chart(m[["Ventas netas", "Compras y gastos netos", "Resultado"]])
    st.line_chart(m[["Caja estimada"]])
    st.caption("El resultado usa valores netos (sin IVA). Los sueldos, honorarios y otros pagos "
               "que no están en el RCV se agregan desde la barra lateral.")

with t2:
    a, b = st.columns(2)
    mix = ventas.groupby("Tipo").agg(Documentos=("Folio", "count"), Neto=("Base", "sum"),
                                     Total=("Total", "sum"))
    t48 = sum(c48.values())
    if t48:
        mix.loc["Comprobantes pago electrónico (48)"] = [float("nan"), t48, round(t48 * 1.19), 0]
    mix["% del neto"] = mix["Neto"] / mix["Neto"].sum()
    a.subheader("Facturas vs. boletas")
    a.dataframe(mix.style.format({"Documentos": "{:,.0f}", "Neto": "{:,.0f}", "Total": "{:,.0f}",
                                  "% del neto": "{:.1%}"}, na_rep="—"),
                width="stretch")
    bol = ventas[ventas["Tipo"] == "Venta boleta"]
    if len(bol):
        a.metric("Ticket promedio boleta (con IVA)", clp(bol["Total"].mean()))
        a.metric("Boleta más alta", clp(bol["Total"].max()))
    b.subheader("Ventas por día de la semana (neto, sin tipo 48)")
    dd = ventas.dropna(subset=["Fecha"]).groupby(ventas["Fecha"].dt.dayofweek)["Base"].sum()
    b.bar_chart(dd.reindex(range(7), fill_value=0).rename(index=dict(enumerate(DIAS))))
    st.subheader("Ventas diarias (neto, sin tipo 48)")
    st.bar_chart(ventas.dropna(subset=["Fecha"]).groupby(ventas["Fecha"].dt.date)["Base"].sum())
    fac = ventas[ventas["Tipo"] == "Venta factura"]
    if len(fac):
        st.subheader("Clientes con factura")
        cl = fac.groupby(["Contraparte", "Nombre"])["Total"].sum().sort_values(ascending=False)
        st.dataframe(cl.reset_index().style.format({"Total": "{:,.0f}"}), width="stretch",
                     hide_index=True)

with t3:
    pr = compras.groupby("Nombre")["Total"].sum().sort_values(ascending=False)
    pr = pr.reset_index()
    pr["% del total"] = pr["Total"] / pr["Total"].sum()
    pr["% acumulado"] = pr["% del total"].cumsum()
    top3 = pr["% del total"].head(3).sum() if len(pr) else 0
    exento = compras["Exento"].sum()
    nc = compras.loc[compras["Doc"] == 61, "Total"].sum()
    k1, k2, k3 = st.columns(3)
    k1.metric("Concentración top 3 proveedores", f"{top3:.0%}")
    k2.metric("Compras exentas de IVA (ej. arriendos)", clp(exento),
              delta=f"{exento / max(compras['Base'].sum(), 1):.0%} de las compras", delta_color="off")
    k3.metric("Notas de crédito recibidas", clp(-nc))
    st.subheader("Proveedores")
    st.dataframe(pr.style.format({"Total": "{:,.0f}", "% del total": "{:.1%}", "% acumulado": "{:.1%}"}),
                 width="stretch", hide_index=True)
    st.bar_chart(pr.head(10).set_index("Nombre")["Total"])

with t4:
    st.subheader(f"Mes promedio con ventas {var}% abajo / arriba")
    v0, c0 = tot["Ventas netas"] / n, tot["Compras y gastos netos"] / n
    filas = []
    for nom, f in [("Pesimista", 1 - var / 100), ("Base", 1.0), ("Optimista", 1 + var / 100)]:
        v = v0 * f
        c = c0 * (1 + (f - 1) * share / 100)
        r = v - c - extra - v * ppm / 100
        filas.append({"Escenario": nom, "Ventas netas": v, "Compras y gastos": c,
                      "Resultado mensual": r, "Margen": r / v if v else 0,
                      "Meses de caja": (caja0 / -r) if r < 0 and caja0 > 0 else None})
    esc = pd.DataFrame(filas)
    st.dataframe(esc.style.format({"Ventas netas": "{:,.0f}", "Compras y gastos": "{:,.0f}",
                                   "Resultado mensual": "{:,.0f}", "Margen": "{:.1%}",
                                   "Meses de caja": "{:.1f}"}, na_rep="—"),
                 width="stretch", hide_index=True)

with t5:
    vista = datos.drop(columns=["Periodo_RCV", "Periodo_Fecha", "Doc"]).sort_values(["Tipo", "Fecha"])
    st.dataframe(vista, width="stretch", hide_index=True)
    st.download_button("⬇️ Descargar consolidado (CSV)", vista.to_csv(index=False).encode("utf-8-sig"),
                       file_name="consolidado_rcv.csv", mime="text/csv")
.0, index=df.index)
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
