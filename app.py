"""Aplicación Streamlit para análisis exploratorio automático de datos."""

from __future__ import annotations

from io import BytesIO
from typing import Iterable

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


st.set_page_config(
    page_title="Explorador automático de datos",
    page_icon="📊",
    layout="wide",
)

PALABRAS_FECHA = ("fecha", "date")


@st.cache_data(show_spinner="Leyendo el archivo...")
def leer_dataset(contenido: bytes, nombre_archivo: str) -> pd.DataFrame:
    """Lee CSV, XLSX o XLS desde memoria y normaliza solo los encabezados."""
    extension = nombre_archivo.rsplit(".", 1)[-1].lower()
    buffer = BytesIO(contenido)

    if extension == "csv":
        # sep=None permite inferir separadores habituales como coma, punto y coma o tabulador.
        try:
            df = pd.read_csv(buffer, sep=None, engine="python")
        except UnicodeDecodeError:
            buffer.seek(0)
            df = pd.read_csv(buffer, sep=None, engine="python", encoding="latin-1")
    elif extension == "xlsx":
        df = pd.read_excel(buffer, engine="openpyxl")
    elif extension == "xls":
        df = pd.read_excel(buffer, engine="xlrd")
    else:
        raise ValueError("Formato no admitido. Cargue un archivo CSV, XLSX o XLS.")

    if df.empty and len(df.columns) == 0:
        return df

    # Se cambian únicamente los nombres, no los valores del dataset.
    df.columns = [str(columna).strip() for columna in df.columns]

    # Se intenta convertir fechas solo cuando el nombre de la columna da una señal clara.
    for columna in df.columns:
        if any(palabra in columna.lower() for palabra in PALABRAS_FECHA):
            try:
                convertida = pd.to_datetime(df[columna], errors="coerce")
                originales_no_nulos = int(df[columna].notna().sum())
                conversiones_validas = int(convertida.notna().sum())
                # Evita destruir columnas cuyo nombre parece fecha pero cuyos valores no lo son.
                if originales_no_nulos == 0 or conversiones_validas / originales_no_nulos >= 0.6:
                    df[columna] = convertida
            except (TypeError, ValueError, OverflowError):
                pass
    return df


def tipo_analitico(serie: pd.Series) -> str:
    """Interpreta el dtype de Pandas como un tipo útil para el análisis."""
    if pd.api.types.is_datetime64_any_dtype(serie):
        return "Fecha/hora"
    if pd.api.types.is_bool_dtype(serie):
        return "Booleana"
    if pd.api.types.is_numeric_dtype(serie):
        return "Numérica"
    no_nulos = serie.dropna()
    if no_nulos.empty:
        return "Texto"
    proporcion_unicos = no_nulos.nunique(dropna=True) / len(no_nulos)
    limite_categorias = max(20, int(len(no_nulos) * 0.05))
    if no_nulos.nunique(dropna=True) <= limite_categorias or proporcion_unicos <= 0.05:
        return "Categórica"
    return "Texto"


def columnas_por_tipo(df: pd.DataFrame, tipos: Iterable[str]) -> list[str]:
    tipos = set(tipos)
    return [col for col in df.columns if tipo_analitico(df[col]) in tipos]


def resumen_variables(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Variable": df.columns,
            "Tipo de dato (Pandas)": [str(df[c].dtype) for c in df.columns],
            "Tipo analítico": [tipo_analitico(df[c]) for c in df.columns],
            "Valores no nulos": [int(df[c].notna().sum()) for c in df.columns],
            "Valores únicos": [int(df[c].nunique(dropna=True)) for c in df.columns],
        }
    )


def tabla_faltantes(df: pd.DataFrame) -> pd.DataFrame:
    faltantes = df.isna().sum()
    porcentaje = (faltantes / len(df) * 100) if len(df) else faltantes.astype(float)
    return (
        pd.DataFrame(
            {
                "Variable": df.columns,
                "Valores faltantes": faltantes.values.astype(int),
                "Porcentaje faltante": porcentaje.values,
            }
        )
        .sort_values(["Valores faltantes", "Variable"], ascending=[False, True])
        .reset_index(drop=True)
    )


def a_csv(df: pd.DataFrame) -> bytes:
    """Genera CSV UTF-8 con BOM en memoria."""
    return df.to_csv(index=False).encode("utf-8-sig")


def aplicar_filtros(df: pd.DataFrame) -> pd.DataFrame:
    """Construye filtros laterales y conserva nulos según los requisitos."""
    filtrado = df.copy()
    st.sidebar.header("Filtros interactivos")

    fecha_cols = columnas_por_tipo(df, ["Fecha/hora"])
    if fecha_cols:
        st.sidebar.subheader("Por fecha")
        seleccion_fechas = st.sidebar.multiselect(
            "Variables de fecha", fecha_cols, key="filtros_fecha"
        )
        for columna in seleccion_fechas:
            fechas_validas = df[columna].dropna()
            if fechas_validas.empty:
                st.sidebar.caption(f"{columna}: sin fechas válidas.")
                continue
            minimo, maximo = fechas_validas.min().date(), fechas_validas.max().date()
            rango = st.sidebar.date_input(
                f"Rango de {columna}",
                value=(minimo, maximo),
                min_value=minimo,
                max_value=maximo,
                key=f"fecha_{columna}",
            )
            if isinstance(rango, (tuple, list)) and len(rango) == 2:
                inicio, fin = pd.Timestamp(rango[0]), pd.Timestamp(rango[1])
                valores = filtrado[columna]
                mascara = valores.isna() | valores.between(
                    inicio, fin + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
                )
                filtrado = filtrado[mascara]

    categoricas = columnas_por_tipo(df, ["Categórica", "Booleana"])
    if categoricas:
        st.sidebar.subheader("Por categorías")
        seleccion_cat = st.sidebar.multiselect(
            "Variables categóricas", categoricas, key="filtros_categoricos"
        )
        for columna in seleccion_cat:
            opciones = df[columna].dropna().unique().tolist()
            opciones = sorted(opciones, key=lambda x: str(x))
            elegidas = st.sidebar.multiselect(
                f"Categorías de {columna}", opciones, default=opciones, key=f"cat_{columna}"
            )
            # Si no se elige ninguna categoría, el filtro produce cero filas de forma explícita.
            filtrado = filtrado[filtrado[columna].isin(elegidas)]

    numericas = columnas_por_tipo(df, ["Numérica"])
    if numericas:
        st.sidebar.subheader("Por rangos numéricos")
        seleccion_num = st.sidebar.multiselect(
            "Variables numéricas", numericas, key="filtros_numericos"
        )
        for columna in seleccion_num:
            validos = pd.to_numeric(df[columna], errors="coerce").dropna()
            if validos.empty:
                st.sidebar.caption(f"{columna}: sin valores numéricos válidos.")
                continue
            minimo, maximo = float(validos.min()), float(validos.max())
            if np.isclose(minimo, maximo):
                st.sidebar.caption(f"{columna}: valor constante ({minimo:g}).")
                continue
            rango = st.sidebar.slider(
                f"Rango de {columna}",
                min_value=minimo,
                max_value=maximo,
                value=(minimo, maximo),
                key=f"num_{columna}",
            )
            valores = pd.to_numeric(filtrado[columna], errors="coerce")
            filtrado = filtrado[valores.isna() | valores.between(rango[0], rango[1])]

    st.sidebar.metric("Registros resultantes", len(filtrado))
    return filtrado


def detectar_atipicos(
    df: pd.DataFrame, variables: list[str], factor: float
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Devuelve registros atípicos detallados y un resumen por variable."""
    resultados = []
    resumen = []
    for columna in variables:
        serie = pd.to_numeric(df[columna], errors="coerce")
        validos = serie.dropna()
        if validos.empty:
            inferior = superior = np.nan
            mascara = pd.Series(False, index=df.index)
        else:
            q1, q3 = validos.quantile([0.25, 0.75])
            iqr = q3 - q1
            inferior = q1 - factor * iqr
            superior = q3 + factor * iqr
            mascara = serie.notna() & ((serie < inferior) | (serie > superior))

        detectados = df.loc[mascara].copy()
        if not detectados.empty:
            detectados.insert(0, "Fila original", detectados.index)
            detectados.insert(1, "Variable con valor atípico", columna)
            detectados.insert(2, "Límite inferior", inferior)
            detectados.insert(3, "Límite superior", superior)
            resultados.append(detectados)
        resumen.append({"Variable": columna, "Cantidad de atípicos": int(mascara.sum())})

    columnas_salida = [
        "Fila original",
        "Variable con valor atípico",
        "Límite inferior",
        "Límite superior",
        *df.columns.tolist(),
    ]
    detalle = (
        pd.concat(resultados, ignore_index=True)
        if resultados
        else pd.DataFrame(columns=columnas_salida)
    )
    return detalle, pd.DataFrame(resumen)


def mostrar_bienvenida() -> None:
    st.info("Cargue un archivo desde la barra lateral para iniciar el análisis.")
    c1, c2, c3 = st.columns(3)
    c1.markdown("### 1. Cargar\nSeleccione un archivo **CSV, XLSX o XLS**.")
    c2.markdown("### 2. Explorar\nAplique filtros y consulte calidad, estadísticas y gráficos.")
    c3.markdown("### 3. Descargar\nExporte los datos filtrados y los valores atípicos.")
    st.markdown(
        """
        #### Análisis disponibles
        - Dimensiones, tipos de variables e indicadores generales.
        - Duplicados, valores faltantes y estadísticas descriptivas.
        - Distribuciones, correlaciones y detección de valores atípicos por IQR.
        - Filtros interactivos, tabla ordenable y descargas en CSV.
        """
    )
    st.warning(
        "Los datos se procesan durante la sesión. Evite cargar información personal, "
        "confidencial o sensible."
    )


def main() -> None:
    st.title("Explorador automático de datos")
    st.write(
        "Cargue un conjunto de datos y obtenga automáticamente un análisis exploratorio "
        "interactivo, sin utilizar rutas fijas ni datos predeterminados."
    )

    st.sidebar.title("Carga del dataset")
    archivo = st.sidebar.file_uploader(
        "Seleccione un archivo", type=["csv", "xlsx", "xls"], accept_multiple_files=False
    )

    if archivo is None:
        mostrar_bienvenida()
        st.stop()

    try:
        df_original = leer_dataset(archivo.getvalue(), archivo.name)
    except Exception as error:
        st.error(
            "No fue posible procesar el archivo. Compruebe que el formato, la codificación "
            "y la estructura sean válidos."
        )
        st.caption(f"Detalle técnico: {type(error).__name__}: {error}")
        st.stop()

    if df_original.empty:
        st.warning("El archivo está vacío o no contiene filas de datos para analizar.")
        st.stop()

    st.sidebar.success(f"Archivo cargado: {archivo.name}")
    df = aplicar_filtros(df_original)
    if df.empty:
        st.warning("Los filtros no producen registros. Ajuste los filtros de la barra lateral.")
        st.stop()

    st.subheader("Indicadores generales")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Filas", df.shape[0])
    m2.metric("Columnas", df.shape[1])
    m3.metric("Duplicados completos", int(df.duplicated().sum()))
    m4.metric("Celdas faltantes", int(df.isna().sum().sum()))
    st.caption(f"Archivo: **{archivo.name}** | Dimensiones actuales: **{df.shape[0]} × {df.shape[1]}**")

    tabs = st.tabs(
        [
            "Resumen y tipos",
            "Calidad de datos",
            "Estadísticas",
            "Distribuciones",
            "Correlaciones",
            "Valores atípicos",
            "Tabla ordenable",
        ]
    )

    with tabs[0]:
        st.subheader("Dimensiones del dataset filtrado")
        st.write(f"Filas: **{df.shape[0]}** | Columnas: **{df.shape[1]}** | Archivo: **{archivo.name}**")
        st.subheader("Tipos de variables")
        st.dataframe(resumen_variables(df), use_container_width=True, hide_index=True)

    with tabs[1]:
        st.subheader("Registros duplicados")
        numero_duplicados = int(df.duplicated().sum())
        st.metric("Filas duplicadas adicionales", numero_duplicados)
        involucrados = df[df.duplicated(keep=False)]
        if involucrados.empty:
            st.success("No se encontraron registros completamente duplicados.")
        else:
            st.write("Todos los registros involucrados en duplicados:")
            st.dataframe(involucrados, use_container_width=True)

        st.subheader("Valores faltantes")
        faltantes = tabla_faltantes(df)
        st.dataframe(
            faltantes.style.format({"Porcentaje faltante": "{:.2f}%"}),
            use_container_width=True,
            hide_index=True,
        )
        con_faltantes = faltantes[faltantes["Valores faltantes"] > 0]
        if con_faltantes.empty:
            st.success("No se encontraron valores faltantes.")
        else:
            figura = px.bar(
                con_faltantes,
                x="Variable",
                y="Porcentaje faltante",
                text_auto=".2f",
                title="Porcentaje de valores faltantes por variable",
            )
            figura.update_layout(yaxis_title="Porcentaje (%)")
            st.plotly_chart(figura, use_container_width=True)

    with tabs[2]:
        st.subheader("Estadísticas descriptivas")
        opcion = st.radio(
            "Variables a resumir",
            ["Todas las variables", "Solo variables numéricas", "Solo variables categóricas"],
            horizontal=True,
        )
        try:
            if opcion == "Solo variables numéricas":
                columnas = columnas_por_tipo(df, ["Numérica"])
                if not columnas:
                    raise ValueError("El dataset filtrado no contiene variables numéricas.")
                estadisticas = df[columnas].describe().T
            elif opcion == "Solo variables categóricas":
                columnas = columnas_por_tipo(df, ["Categórica", "Texto", "Booleana"])
                if not columnas:
                    raise ValueError("El dataset filtrado no contiene variables categóricas o de texto.")
                estadisticas = df[columnas].describe(include="all").T
            else:
                estadisticas = df.describe(include="all").T
            traduccion = {
                "count": "Conteo", "mean": "Media", "std": "Desviación estándar",
                "min": "Mínimo", "25%": "Primer cuartil", "50%": "Mediana",
                "75%": "Tercer cuartil", "max": "Máximo", "unique": "Valores únicos",
                "top": "Categoría más frecuente", "freq": "Frecuencia dominante",
            }
            estadisticas = estadisticas.rename(columns=traduccion)
            estadisticas.index.name = "Variable"
            st.dataframe(estadisticas, use_container_width=True)
        except (ValueError, TypeError) as error:
            st.info(str(error))

    with tabs[3]:
        st.subheader("Distribuciones")
        variable = st.selectbox("Seleccione una variable", df.columns)
        tipo = tipo_analitico(df[variable])
        if tipo == "Numérica":
            intervalos = st.slider("Número de intervalos", 5, 100, 30)
            histograma = px.histogram(
                df, x=variable, nbins=intervalos, title=f"Histograma de {variable}"
            )
            st.plotly_chart(histograma, use_container_width=True)

            categorias = columnas_por_tipo(df, ["Categórica", "Booleana"])
            opciones_agrupacion = ["Sin agrupación", *[c for c in categorias if c != variable]]
            agrupacion = st.selectbox("Agrupar diagrama de caja", opciones_agrupacion)
            argumentos = {"x": agrupacion, "y": variable} if agrupacion != "Sin agrupación" else {"y": variable}
            caja = px.box(df, points="outliers", title=f"Diagrama de caja de {variable}", **argumentos)
            st.plotly_chart(caja, use_container_width=True)
        else:
            valores = df[variable].astype("object").where(df[variable].notna(), "(Faltante)")
            frecuencias = valores.value_counts(dropna=False).rename_axis("Categoría").reset_index(name="Frecuencia")
            if len(frecuencias) > 30:
                st.info("Se muestran las 30 categorías más frecuentes.")
                frecuencias = frecuencias.head(30)
            frecuencias["Categoría"] = frecuencias["Categoría"].astype(str)
            barras = px.bar(
                frecuencias, x="Categoría", y="Frecuencia", title=f"Frecuencias de {variable}"
            )
            st.plotly_chart(barras, use_container_width=True)
            st.dataframe(frecuencias, use_container_width=True, hide_index=True)

    with tabs[4]:
        st.subheader("Correlaciones")
        numericas = columnas_por_tipo(df, ["Numérica"])
        if len(numericas) < 2:
            st.info("Se necesitan al menos dos variables numéricas para calcular correlaciones.")
        else:
            elegidas = st.multiselect("Variables numéricas", numericas, default=numericas)
            metodo_etiqueta = st.selectbox("Método", ["Pearson", "Spearman", "Kendall"])
            if len(elegidas) < 2:
                st.warning("Seleccione al menos dos variables numéricas.")
            else:
                matriz = df[elegidas].corr(method=metodo_etiqueta.lower())
                calor = go.Figure(
                    data=go.Heatmap(
                        z=matriz.values,
                        x=matriz.columns,
                        y=matriz.index,
                        zmin=-1,
                        zmax=1,
                        colorscale="RdBu_r",
                        text=np.round(matriz.values, 2),
                        texttemplate="%{text}",
                        hovertemplate="%{y} / %{x}: %{z:.3f}<extra></extra>",
                    )
                )
                calor.update_layout(title=f"Correlación de {metodo_etiqueta}")
                st.plotly_chart(calor, use_container_width=True)
                st.dataframe(matriz.style.format("{:.3f}"), use_container_width=True)
        st.caption("Una correlación no implica causalidad.")

    with tabs[5]:
        st.subheader("Valores atípicos mediante rango intercuartílico")
        numericas = columnas_por_tipo(df, ["Numérica"])
        if not numericas:
            st.info("El dataset filtrado no contiene variables numéricas.")
            detalle_atipicos = pd.DataFrame()
        else:
            variables = st.multiselect("Variables numéricas", numericas, default=numericas)
            factor = st.slider("Factor IQR", 1.0, 3.0, 1.5, 0.1)
            if not variables:
                st.info("Seleccione una o varias variables numéricas.")
                detalle_atipicos = pd.DataFrame()
            else:
                detalle_atipicos, resumen_atipicos = detectar_atipicos(df, variables, factor)
                st.metric("Detecciones de valores atípicos", len(detalle_atipicos))
                grafico = px.bar(
                    resumen_atipicos,
                    x="Variable",
                    y="Cantidad de atípicos",
                    text_auto=True,
                    title="Cantidad de valores atípicos por variable",
                )
                st.plotly_chart(grafico, use_container_width=True)
                if detalle_atipicos.empty:
                    st.success("No se detectaron valores atípicos con la configuración actual.")
                else:
                    st.dataframe(detalle_atipicos, use_container_width=True, hide_index=True)
                st.download_button(
                    "Descargar valores atípicos",
                    data=a_csv(detalle_atipicos),
                    file_name="valores_atipicos.csv",
                    mime="text/csv",
                )
        st.caption("Un valor atípico no necesariamente representa un error.")

    with tabs[6]:
        st.subheader("Tabla interactiva y ordenable")
        visibles = st.multiselect("Columnas visibles", df.columns, default=list(df.columns))
        if not visibles:
            st.info("Seleccione al menos una columna para mostrar la tabla.")
        else:
            st.dataframe(df[visibles], use_container_width=True, hide_index=True, height=500)
        st.download_button(
            "Descargar datos filtrados",
            data=a_csv(df),
            file_name="datos_filtrados.csv",
            mime="text/csv",
        )

    st.divider()
    st.info(
        "Responsabilidad sobre los datos: la información se procesa durante la sesión de la "
        "aplicación. Evite cargar datos personales, confidenciales o sensibles. Este análisis "
        "exploratorio no reemplaza la interpretación experta. Una correlación no implica "
        "causalidad y un valor atípico no necesariamente representa un error."
    )


if __name__ == "__main__":
    main()
