import streamlit as st
import pandas as pd
import numpy as np
from streamlit_folium import st_folium
import folium
import local_p_i as lp
import data_bckb as db
from shapely.geometry import Point
import time

def notify_on_upload(file_object, key_name):
    """
    Checks if a file is newly uploaded and triggers a toast.
    key_name: a unique string like 'stratum' or 'rivers'
    """
    # Create a unique key in session_state for this specific uploader
    state_key = f"last_file_{key_name}"
    
    if state_key not in st.session_state:
        st.session_state[state_key] = None

    if file_object is not None:
        # Only trigger if the name is different from what we remember
        if st.session_state[state_key] != file_object.name:
            st.toast(f"Layer Loaded: {file_object.name}", icon="✅")
            # Update the 'memory'
            st.session_state[state_key] = file_object.name
            return True
    return False

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="SMCDSS Wastewater Tool", layout="wide")

st.title("♻️🌊 SMCDSS: DEWATS Systems")
st.markdown("Support algorithm for the definition of decentralized systems for greywater recirculation")

#SIDEBAR
with st.sidebar:

    st.header("General Parameters")
    
    # Project Type
    project_options = {
        "Residential Property with Lot Autonomy": "Residential Building",
        "Housing Unit under Horizontal Property Regime":"Single-family Flat",
        "Community Residential Core": "Neighborhood",
        "Large-Scale Urban Development Project": "Urban Development"
    }
    project_type = st.selectbox("Project Type", options=list(project_options.keys()))

    # Graywater Sources
    greywater_comp = ['Fats, Oils, and Grease','Chlorine and Disinfectants', 'Detergents and Surfactants', 'Coarse Suspended Solids and Non-Biodegradable Material']

    # Streamlit Multi-select
    greywater_con = st.multiselect(
        "Inhibitory Substances or Critical Contaminants:",
        options=list(greywater_comp),
        help="Identify the presence of inhibitory agents or contaminants in the raw wastewater."
    )

    # Presence of oil
    # Toggle widget acting as the "Flip" button
    grease_trap = st.toggle(
        label="Use of Grease Trap", 
        value=False,
        help="Enable this option if the system includes a grease trap to treat fatty residues or vegetable/animal oils."
    )

    # Water Reuse Purpose
    reuse_options = {
        "Indoor Urban Reuse (Toilet flushing, laundry)": "Toilet flushing",
        "Non-Potable Outdoor Urban Reuse (Street washing / Car washing)": "Street/Car Washing",
        "Unrestricted Irrigation": "Irrigation",
        "Restricted Agriculture / Aquaculture": "Outdoor cleaning",
        "Industrial Cooling": "Industrial use"
    }
    reuse_purpose = st.selectbox("Reuse Purpose", options=list(reuse_options.keys()))  

    st.divider()

    #SIDEBAR: RELATIVE WEIGHTS
    st.header("Relative Weights (%)")
    st.info("The sum must be 100%")
    
    w_econ = st.slider("Economic", 0, 100, 33)
    w_soc = st.slider("Social", 0, 100, 33)
    w_tech = st.slider("Technical", 0, 100, 34)
    
    total_w = w_econ + w_soc + w_tech
    
    if total_w == 100:
        st.success(f"General Balance: {total_w}%")
    else:
        st.error(f"Total: {total_w}%. Please Adjust to 100%.")

#SPATIAL DATA (MAP)
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("Location")
    m = folium.Map(
        location=[0, 0], 
        zoom_start=1.5,     # A zoom of 1 to 2 shows the whole world
        min_zoom=1,         # Prevents zooming out further into grey space
        no_wrap=False       # Set to True if you want to prevent the map from repeating horizontally
    )
    
    # Allow user to click and get coordinates
    m.add_child(folium.LatLngPopup())
    map_data = st_folium(m, height=500, width=700)

with col2:

    st.subheader("Technical Constraints")
    # Additional engineering inputs suggested previously
    population = st.number_input(
        "Estimated Population", 
        min_value=1, 
        value=50,
        help= "Enter the estimated population to be served by the system.")

    available_area = st.number_input(
        "Available Area (m²):", 
        min_value=0.0, 
        step=1.0, 
        help="Total footprint available for the construction of the treatment system"
    )

    # Display summary of selections for logic verification
    st.write("---")
    st.write("**Summary:**")
    st.write(f"Type: {project_type}")
    st.write(f"Reuse Purpose: {reuse_purpose}")
    if map_data['last_clicked']:
        st.write(f"Coordinates: {map_data['last_clicked']['lat']:.4f}, {map_data['last_clicked']['lng']:.4f}")

# --- 5. EXECUTION BUTTON ---
if st.button("Execute Analysis", disabled=(total_w != 100)):
    st.toast('Analisys in process...', icon='⚙️')
    st.write("### Results")

    #Getting the coordinates from the user interface
    st.info("Analysis engine is ready to receive data from your backbone...")
    
    if map_data['last_clicked']:

        user_lat = map_data['last_clicked']['lat']
        user_lon = map_data['last_clicked']['lng']
    
        st.write(f"📍 Selected Location: {user_lat:.4f}, {user_lon:.4f}")
        project_params = {
            'point' : Point(user_lon,user_lat),
            'project type': project_type,
            'reuse purpose' : reuse_purpose,
            'p_gtrap': grease_trap,
            'contaminants' : greywater_con,
            'population' : population,
            'av_area' : available_area,
            'w_econ': w_econ,
            'w_tech': w_tech,
            'w_soc': w_soc
        }
        if "analysis_done" not in st.session_state:
            st.session_state.analysis_done = False
        if "final_df" not in st.session_state:
            st.session_state.final_df = None
        
        excel_data = db.evaluate_ind(project_params)

        if st.session_state.analysis_done:
            st.subheader("Analysis Results")
            st.dataframe(st.session_state.final_df)

            # The download button appears dynamically right here
            st.download_button(
                label="📥 Download Totalized Tables (Excel)",
                data=excel_data,
                file_name="SCDMSS_Totalized_Report.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )


    else:
        st.warning("Please click a location on the map to start the analysis.")

    #Call to the logic function
    st.toast('Suitability map generated!', icon='✅')