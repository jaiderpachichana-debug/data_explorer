Explorador automático de datos
Descripción
Aplicación web desarrollada con Streamlit para cargar archivos CSV, XLSX o XLS y ejecutar un análisis exploratorio de datos de forma automática. No utiliza un dataset predeterminado, rutas fijas, claves ni almacenamiento permanente de los archivos cargados.
Funcionalidades
Carga de archivos desde el navegador.
Limpieza de espacios en los nombres de columnas e intento prudente de reconocimiento de fechas.
Filtros por fecha, categorías y rangos numéricos.
Indicadores de filas, columnas, duplicados y celdas faltantes.
Tabla de tipos de variables y tipos analíticos.
Revisión de duplicados y valores faltantes.
Estadísticas descriptivas numéricas y categóricas.
Histogramas, diagramas de caja y gráficos de frecuencias con Plotly.
Correlaciones de Pearson, Spearman y Kendall.
Detección de valores atípicos mediante el método IQR.
Tabla interactiva con selección de columnas.
Descarga en CSV UTF-8 con BOM de datos filtrados y valores atípicos.
Formatos admitidos
`.csv`
`.xlsx`, leído con `openpyxl`
`.xls`, leído con `xlrd`
Estructura del repositorio
```text
explorador-automatico-datos/
├── app.py
├── requirements.txt
└── README.md
```
No se incluye ningún dataset.
Instalación
Instale Python 3.10 o una versión compatible.
Clone o descargue este repositorio.
Cree y active un entorno virtual:
```bash
python -m venv .venv
```
En Windows PowerShell:
```powershell
.venv\Scripts\Activate.ps1
```
En macOS o Linux:
```bash
source .venv/bin/activate
```
Instale las dependencias:
```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```
Ejecución local
Desde la carpeta del proyecto, ejecute:
```bash
streamlit run app.py
```
Streamlit abrirá la aplicación en el navegador. Si no ocurre automáticamente, utilice la dirección local mostrada en la terminal.
Despliegue en Streamlit Community Cloud
Cree un repositorio en GitHub y suba `app.py`, `requirements.txt` y `README.md` a la rama principal.
Inicie sesión en Streamlit Community Cloud con su cuenta de GitHub.
Seleccione la opción para crear una aplicación nueva.
Elija el repositorio, la rama principal y `app.py` como archivo de entrada.
Inicie el despliegue. La plataforma instalará las dependencias declaradas en `requirements.txt`.
Revise los registros de despliegue si la aplicación no inicia.
La aplicación no necesita secretos ni variables de entorno.
Privacidad de los datos
Los datos se procesan durante la sesión de la aplicación. Evite cargar información personal, confidencial o sensible. En un despliegue público, la responsabilidad sobre el contenido cargado corresponde al usuario y a la política de tratamiento de datos de la organización.
Limitaciones conocidas
Los archivos muy grandes pueden superar la memoria o el límite de carga del entorno de despliegue.
La inferencia automática de separadores, codificación, fechas y tipos puede requerir revisión humana.
Se analiza la primera hoja de los archivos Excel.
Las columnas de texto con baja cardinalidad se interpretan como categóricas mediante una regla heurística.
Pearson, Spearman y Kendall solo se aplican a variables numéricas.
La detección IQR es un criterio exploratorio. Un valor atípico no necesariamente es un error.
Una correlación no demuestra causalidad.
Los filtros categóricos no incluyen los valores faltantes como categoría seleccionable.
