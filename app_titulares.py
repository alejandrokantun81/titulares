import streamlit as st
import pandas as pd

# CONFIGURACIÓN DE PÁGINA
st.set_page_config(page_title="Auditoría Titulares", layout="wide", page_icon="⚖️")

# ESTILOS VISUALES
st.markdown("""
<style>
    .stContainer {border-radius: 10px;}
    div[data-testid="stMetricValue"] {font-size: 1.1rem;}
</style>
""", unsafe_allow_html=True)

# 1. CARGA DE DATOS (LECTURA DIRECTA DE EXCEL)
@st.cache_data
def cargar_datos():
    archivo = 'DZITAS TITULARES 2025B.xlsx'
    
    try:
        # Leemos el Excel directamente. 
        # header=5 porque la fila de títulos ("ID DEL DOCENTE"...) está en la fila 6 (índice 5)
        # sheet_name=None lee todas, pero especificamos 'PLANTILLA TIT' o leemos la activa (0)
        # Probamos leer la hoja específica primero
        try:
            df = pd.read_excel(archivo, sheet_name='PLANTILLA TIT', header=5, engine='openpyxl')
        except:
            # Si falla el nombre de la hoja, leemos la primera hoja disponible
            df = pd.read_excel(archivo, header=5, engine='openpyxl')
            
    except FileNotFoundError:
        return None

    # LIMPIEZA DE DATOS
    cols_identidad = [
        'ID DEL DOCENTE', 'APELLIDO PATERNO', 'APELLIDO MATERNO', 'NOMBRE (S)',
        'NÓMINA', 'HRS PLAZA/BASE', 'HRS CONTRATO', 'INFORMACIÓN ACADÉMICA '
    ]
    
    # Rellenar hacia abajo (Forward Fill)
    # Verificamos que las columnas existan antes de procesar
    cols_existentes = [c for c in cols_identidad if c in df.columns]
    if cols_existentes:
        df[cols_existentes] = df[cols_existentes].ffill()
    
    # Crear Nombre Completo
    df['DOCENTE'] = df['NOMBRE (S)'].fillna('') + ' ' + df['APELLIDO PATERNO'].fillna('') + ' ' + df['APELLIDO MATERNO'].fillna('')
    
    # Convertir números
    cols_numericas = ['HRS. POR UAC/ASIG', 'NÓMINA', 'HRS PLAZA/BASE', 'HRS CONTRATO']
    for col in cols_numericas:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    return df

df = cargar_datos()

if df is None:
    st.error(f"⚠️ **Archivo no encontrado.** \n\nPor favor sube a GitHub el archivo: `DZITAS TITULARES 2025B.xlsx`")
    st.stop()

# 2. INTERFAZ DE AUDITORÍA
st.title("🛡️ Sistema de Control de Plazas")
st.markdown(f"**Archivo cargado:** `DZITAS TITULARES 2025B.xlsx`")

# Filtros
col_search, col_filter = st.columns([2, 1])
busqueda = col_search.text_input("🔍 Buscar Docente...", placeholder="Escribe nombre o ID...")
filtro_status = col_filter.selectbox("Estado", ["Todos", "✅ Coherente", "❌ Excedido / Error"])

# Procesamiento Lógico
if 'ID DEL DOCENTE' in df.columns:
    docentes_unicos = df['ID DEL DOCENTE'].unique()
    docentes_filtrados = []

    for doc_id in docentes_unicos:
        # Datos del docente
        sub_df = df[df['ID DEL DOCENTE'] == doc_id]
        if sub_df.empty: continue
        
        primer = sub_df.iloc[0]
        
        # CÁLCULOS
        capacidad_nomina = primer.get('NÓMINA', 0)
        
        # Materias reales
        materias = sub_df.dropna(subset=['UNIDAD DE APRENDIZAJE CURRICULAR/ASIGNATURA'])
        carga_asignada = materias['HRS. POR UAC/ASIG'].sum()
        
        # VALIDACIÓN (SEMÁFORO)
        es_excedido = carga_asignada > (capacidad_nomina + 0.1) # Margen de tolerancia 0.1
        
        # Objeto Docente
        d = {
            "id": doc_id,
            "nombre": primer['DOCENTE'],
            "nomina": capacidad_nomina,
            "base": primer.get('HRS PLAZA/BASE', 0),
            "contrato": primer.get('HRS CONTRATO', 0),
            "carga": carga_asignada,
            "es_excedido": es_excedido,
            "materias": materias
        }
        
        # Filtrado
        match_txt = str(busqueda).lower() in str(d['nombre']).lower() or str(busqueda) in str(d['id'])
        match_stat = True
        if filtro_status == "✅ Coherente" and d['es_excedido']: match_stat = False
        if filtro_status == "❌ Excedido / Error" and not d['es_excedido']: match_stat = False
        
        if match_txt and match_stat:
            docentes_filtrados.append(d)

    # KPIs
    kpi1, kpi2, kpi3 = st.columns(3)
    kpi1.metric("Total Docentes", len(docentes_filtrados))
    errores = sum(1 for x in docentes_filtrados if x['es_excedido'])
    kpi2.metric("Con Errores/Excedidos", errores, delta=-errores, delta_color="inverse")
    
    st.divider()

    # TARJETAS
    cols = st.columns(2)
    for i, doc in enumerate(docentes_filtrados):
        with cols[i % 2]:
            borde = "red" if doc['es_excedido'] else "green"
            with st.container(border=True):
                c1, c2 = st.columns([3,1])
                c1.markdown(f"**{doc['nombre']}**")
                if doc['es_excedido']:
                    c2.error("ERROR")
                else:
                    c2.success("OK")
                
                # Barra de comparación
                st.caption(f"Capacidad Nómina: {int(doc['nomina'])} hrs")
                st.progress(min(doc['carga'] / (doc['nomina'] if doc['nomina'] > 0 else 1), 1.0))
                
                if doc['es_excedido']:
                    st.markdown(f":red[**Asignadas: {doc['carga']} hrs**] (Sobran {doc['carga']-doc['nomina']})")
                else:
                    st.markdown(f":green[**Asignadas: {doc['carga']} hrs**]")

                with st.expander("Ver Materias"):
                    st.dataframe(doc['materias'][['UNIDAD DE APRENDIZAJE CURRICULAR/ASIGNATURA', 'HRS. POR UAC/ASIG']], hide_index=True)
else:
    st.error("No encontré la columna 'ID DEL DOCENTE'. Revisa la fila de encabezados en el Excel.")