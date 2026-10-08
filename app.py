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
