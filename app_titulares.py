import streamlit as st
import pandas as pd

# CONFIGURACIÓN DE PÁGINA
st.set_page_config(page_title="Auditoría Titulares", layout="wide", page_icon="⚖️")

# ESTILOS VISUALES
st.markdown("""
<style>
    .stContainer {border-radius: 10px;}
    div[data-testid="stMetricValue"] {font-size: 1.1rem;}
    .cat-item {
        background-color: #f1f5f9;
        padding: 4px 8px;
        border-radius: 4px;
        margin-bottom: 4px;
        font-size: 0.85em;
        font-family: monospace;
        color: #334155;
    }
</style>
""", unsafe_allow_html=True)

# 1. CARGA DE DATOS
@st.cache_data
def cargar_datos():
    archivo = 'DZITAS TITULARES 2025B.xlsx'
    
    try:
        # Intentamos leer la hoja específica
        try:
            df = pd.read_excel(archivo, sheet_name='PLANTILLA TIT', header=5, engine='openpyxl')
        except:
            df = pd.read_excel(archivo, header=5, engine='openpyxl')
            
    except FileNotFoundError:
        return None

    # LIMPIEZA DE DATOS
    
    # A) Columnas que SÍ deben rellenarse hacia abajo (Datos fijos del docente)
    cols_identidad = [
        'ID DEL DOCENTE', 'APELLIDO PATERNO', 'APELLIDO MATERNO', 'NOMBRE (S)',
        'NÓMINA', 'HRS PLAZA/BASE', 'HRS CONTRATO', 'INFORMACIÓN ACADÉMICA '
    ]
    
    # Verificamos que existan
    cols_existentes = [c for c in cols_identidad if c in df.columns]
    if cols_existentes:
        df[cols_existentes] = df[cols_existentes].ffill()
    
    # B) Crear Nombre Completo
    df['DOCENTE'] = df['NOMBRE (S)'].fillna('') + ' ' + df['APELLIDO PATERNO'].fillna('') + ' ' + df['APELLIDO MATERNO'].fillna('')
    
    # C) Convertir números (limpieza básica)
    cols_numericas = ['HRS. POR UAC/ASIG', 'NÓMINA', 'HRS PLAZA/BASE', 'HRS CONTRATO']
    for col in cols_numericas:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # NOTA: NO rellenamos 'CATEGORÍAS/ NÓMINA' para poder leer los renglones individuales
    
    return df

df = cargar_datos()

if df is None:
    st.error(f"⚠️ **Archivo no encontrado.** \n\nPor favor sube a GitHub el archivo: `DZITAS TITULARES 2025B.xlsx`")
    st.stop()

# 2. INTERFAZ DE AUDITORÍA
st.title("🛡️ Sistema de Control de Plazas")
st.markdown(f"**Archivo activo:** `DZITAS TITULARES 2025B.xlsx`")

# Filtros
col_search, col_filter = st.columns([2, 1])
busqueda = col_search.text_input("🔍 Buscar Docente...", placeholder="Escribe nombre o ID...")
filtro_status = col_filter.selectbox("Estado", ["Todos", "✅ Coherente", "❌ Excedido / Error"])

# Procesamiento Lógico
if 'ID DEL DOCENTE' in df.columns:
    docentes_unicos = df['ID DEL DOCENTE'].dropna().unique()
    docentes_filtrados = []

    for doc_id in docentes_unicos:
        # Obtenemos TODAS las filas de este docente (incluso las que no tienen materia pero tienen categoría)
        sub_df = df[df['ID DEL DOCENTE'] == doc_id]
        if sub_df.empty: continue
        
        primer = sub_df.iloc[0]
        
        # 1. Extraer desglose de Categorías (NUEVO)
        # Tomamos la columna, quitamos vacíos, convertimos a texto y quitamos duplicados
        if 'CATEGORÍAS/ NÓMINA' in sub_df.columns:
            lista_categorias = sub_df['CATEGORÍAS/ NÓMINA'].dropna().astype(str).unique().tolist()
        else:
            lista_categorias = ["Sin datos"]

        # 2. Cálculos Numéricos
        capacidad_nomina = primer.get('NÓMINA', 0)
        
        # Materias reales (filas que sí tienen nombre de materia)
        materias = sub_df.dropna(subset=['UNIDAD DE APRENDIZAJE CURRICULAR/ASIGNATURA'])
        carga_asignada = materias['HRS. POR UAC/ASIG'].sum()
        
        # 3. Validación
        es_excedido = carga_asignada > (capacidad_nomina + 0.1)
        
        # Objeto Docente
        d = {
            "id": doc_id,
            "nombre": primer['DOCENTE'],
            "nomina": capacidad_nomina,
            "base": primer.get('HRS PLAZA/BASE', 0),
            "contrato": primer.get('HRS CONTRATO', 0),
            "carga": carga_asignada,
            "es_excedido": es_excedido,
            "materias": materias,
            "desglose_categorias": lista_categorias # Guardamos la lista
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

    # RENDERIZADO DE TARJETAS
    cols = st.columns(2)
    for i, doc in enumerate(docentes_filtrados):
        with cols[i % 2]:
            with st.container(border=True):
                # Encabezado
                c1, c2 = st.columns([3,1])
                c1.markdown(f"**{doc['nombre']}**")
                if doc['es_excedido']:
                    c2.error("ERROR")
                else:
                    c2.success("OK")
                
                st.caption(f"ID: {int(doc['id'])}")
                
                # --- NUEVO: MENÚ DESPLEGABLE DE CATEGORÍAS ---
                with st.expander("📂 Ver Desglose de Plazas (Categorías)"):
                    if doc['desglose_categorias']:
                        for cat in doc['desglose_categorias']:
                            # Renderizamos cada categoría como un pequeño bloque
                            st.markdown(f"<div class='cat-item'>{cat}</div>", unsafe_allow_html=True)
                    else:
                        st.text("No especificado")
                # ---------------------------------------------

                # Barra de comparación
                st.markdown(f"**Nómina Total:** {int(doc['nomina'])} hrs")
                
                # Lógica visual de barra de progreso
                ratio = 0
                if doc['nomina'] > 0:
                    ratio = doc['carga'] / doc['nomina']
                
                st.progress(min(ratio, 1.0))
                
                if doc['es_excedido']:
                    st.markdown(f":red[⚠️ **Asignadas: {doc['carga']} hrs**] (Excede por {doc['carga']-doc['nomina']})")
                else:
                    st.markdown(f":green[**Asignadas: {doc['carga']} hrs**] (Disponible: {doc['nomina'] - doc['carga']})")

                with st.expander("Ver Materias Asignadas"):
                    st.dataframe(doc['materias'][['UNIDAD DE APRENDIZAJE CURRICULAR/ASIGNATURA', 'HRS. POR UAC/ASIG']], hide_index=True)
else:
    st.error("No encontré la columna 'ID DEL DOCENTE'. Revisa el archivo.")
