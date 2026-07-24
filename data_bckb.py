import pandas as pd
import local_p_i as lp
import streamlit as st

def evaluate_ind(params):

    r_weight_m = {
        "Criteria": ["Project_size", "Inv_system", "O&M_Costs", "Management_O&M_KN", "Peri-urban_exp_areas", "Reuse", "Sew_cover", "Area", "Dist_treatment_point", "Topography", "Climate", "Resource Recovery", "Energy availability", "Environmental risk", "Population size", "Social participation", "Legal_Complexity", "Supply_Chain_Risk", "Asset_lifespan", "Population density", "Water stress resilience", "Sludge production", "Smell_noise", "Org_Removal_Eff", "Nut_Removal_Eff", "Pathogen_Inactivation"],
        "CW": [0, 0.5, 0.75, 0.75, 1, 0, 0.25, 0.25, 0.75, 1, 0, 0.75, 1, 0.5, 0.5, 0.75, 0, 0.75, 1, 0.25, 0.75, 0.75, 0.5, 0.5, 0.25, 0.5],
        "UASB": [0, 0.5, 0.75, 0.75, 0.5, 0, 0.5, 0.5, 0.5, 0.25, 0, 1, 0.75, 0.5, 0.75, 0.5, 0, 0.75, 0.75, 0.5, 0.25, 0.75, 0.5, 0.5, 0.25, 0.5],
        "SBR": [0, 0.25, 0.25, 0.25, 0.25, 0, 0.75, 1, 0.25, 0.25, 0, 0, 0.25, 0.75, 0.75, 0.25, 0, 0.25, 0.5, 1, 1, 0.25, 0.75, 1, 1, 0.75],
        "VF": [0, 0.75, 0.75, 0.5, 0.5, 0, 0.25, 0.25, 0.5, 0.5, 0, 0.75, 0.75, 0.25, 0.25, 0.75, 0, 0.5, 0.5, 0.25, 0.75, 1, 0.5, 0.75, 0.5, 0.5],
        "AF": [0, 0.75, 0.5, 0.75, 0.75, 0, 0.25, 0.5, 0.5, 0.25, 0, 0.5, 0.75, 0.5, 0.25, 0.5, 0, 0.75, 0.75, 0.25, 0.25, 0.75, 0.75, 0.5, 0.25, 0.75],
        "RBC": [0, 0.5, 0.5, 0.75, 0.5, 0, 0.5, 0.75, 0.25, 0.25, 0, 0.25, 0.75, 0.75, 0.5, 0.25, 0, 0.5, 0.25, 0.25, 0.25, 0.25, 0.75, 0.5, 0.5, 0.5],
        "ST+SAS": [0, 0.75, 0.75, 1, 1, 0, 0.25, 0.25, 0.25, 0.5, 0, 0, 1, 0, 0.25, 0.75, 0, 1, 1, 0.25, 0.75, 0.5, 0.25, 0.5, 0.25, 0.75],
        "MBR": [0, 0.25, 0.25, 0.25, 0.25, 0, 1, 1, 0.5, 0.25, 0, 0, 0.25, 1, 1, 0.25, 0, 0.25, 0, 1, 1, 0.75, 1, 1, 1, 1],
        "Type": ["Economic", "Economic", "Economic", "Economic", "Economic", "Technical", "Technical", "Technical", "Technical", "Technical", "Technical", "Technical", "Technical", "Social", "Technical", "Social", "Social", "Technical", "Technical", "Technical", "Technical", "Technical", "Social", "Technical", "Technical", "Technical"],
        "Variable": ["Proj_type", "Socioeconomic_tier", "Socioeconomic_tier", "Urb_area", "Peri_urb", "Green_areas", "Sew_Dist", "Area", "Dist_ptar", "Slope", "Climate", "Proj_type", "En_grid", "Green_areas", "Population", "Proj_type", "Proj_type", "Proj_type", "Proj_type", "Population_den", "Sup_grid", "Dist_road", "Res_zone", "Proj_type", "Proj_type", "Proj_type"],
        "Inverse": [False, False, False, False, False, True, False, True, False, True, False, False, False, True, True, False, False, False, False, False, False, False, False, False, False, False],
    }

    i_ranges_df = {
        "Variable": ["Proj_type", "Socioeconomic_tier", "Socioeconomic_tier", "Urb_area", "Peri_urb", "Green_areas", "Sew_Dist", "Area", "Dist_ptar", "Slope", "Climate", "Proj_type", "En_grid", "Green_areas", "Population", "Proj_type", "Proj_type", "Proj_type", "Proj_type", "Population_den", "Sup_grid", "Dist_road", "Res_zone", "Proj_type", "Proj_type", "Proj_type"],
        "Max": [1, 4, 4, 1, 1, 5000, 2000, 4000, 10000, 30, 1, 1, 5000, 5000, 5000, 1, 1, 1, 1, 650, 5000, 5000, 1, 1, 1, 1],
        "Min": [0, 1, 1, 0, 0, 0, 0, 1, 0, 1, 0, 0, 0, 0, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    }

    r_weight = pd.DataFrame(r_weight_m).set_index("Criteria")

    #Ranges for normalization process

    ind_range = pd.DataFrame(i_ranges_df).set_index("Variable")

    #Managing the absolute weights of each indicator

    ind_data = pd.DataFrame(r_weight_m).set_index("Variable")

    ind_data['Value'] = 0.0
    ind_data = ind_data[['Inverse','Value']]
    
    p_type(params['project type'], params['population'],r_weight)
    r_type(params['reuse purpose'], r_weight)
    pg_ind(params['contaminants'],params['p_gtrap'],r_weight)

    values = lp.evaluate_values(params)

    tech_uf(params['av_area'],params['population'],values['Socioeconomic_tier'],params['project type'],values['Peri_urb'],r_weight)
    climate_buffer = lp.extract_macro_climate(params['point'])
    st.write(climate_buffer)
    climate_weights(climate_buffer['macro_environmental_zone'],r_weight)
    values = pd.DataFrame([values],index= ['Value']).T
    st.write(values)
    st.write(ind_data)
    ind_data.update(values)
    n_data = norm_criteria(ind_data, ind_range)
    calc_pweight(r_weight,params['w_econ'],params['w_tech'],params['w_soc'])
    final_weighted_matrix = t_weight(n_data, r_weight)
    final_score = final_weighted_matrix.sum().reset_index()
    final_score.columns = ['System','Final Score']
    final_score = final_score.sort_values(by= 'Final Score', ascending= False)
    st.write("Value results:", n_data)
    st.write("Weighted Results:", final_weighted_matrix)
    st.write("Final Scores:", final_score)

    output_d = {
        'n_data': n_data,
        'w_results': final_weighted_matrix,
        'f_scores': final_score
    }

    processed_data = lp.to_excel(output_d)

    st.session_state.final_df = final_score
    st.session_state.analysis_done = True
    
    return processed_data

def t_weight(n_data, r_weights):
    # 1. Filter for numbers
    r_numeric = r_weights.select_dtypes(include=['number'])
    
    # 2. Check dimensions
    if len(n_data) != len(r_numeric):
        msg = f"Row mismatch! Weights: {len(r_numeric)}, Normalized: {len(n_data)}"
        st.error(msg)
        st.stop() # Prevents the return error entirely
    
    # 3. Perform multiplication using .values to bypass index alignment
    # Ensure n_data has the column 'N_Data' as expected
    r_matrix = r_numeric.multiply(n_data['N_Data'].values, axis=0)
    
    return r_matrix

def norm_criteria(ind_data, ranges_df):
    """
    Normalizes indicators even with duplicate names, using a separate ranges table.
    
    Parameters:
    - ind_data: DataFrame with 'Value' column and 'Inverse' logic. Index is Indicator names.
    - ranges_df: DataFrame with unique 'min' and 'max' per Indicator. Index is Indicator names.
    - direction_col: The column name that holds 'normal' or 'inverse' strings.
    """
    # 1. Create a copy to avoid modifying the original data
    df = ind_data.copy()
    
    v_min = ranges_df['Min'].values
    v_max = ranges_df['Max'].values
    v_actual = df['Value'].values

    # Perform the element-wise calculation
    normalized_values = (v_actual - v_min) / (v_max - v_min)

    inv_mask = df['Inverse'].values
    normalized_values[inv_mask] = 1 - normalized_values[inv_mask]

    df['N_Data'] = normalized_values

    return df

def r_type(r_purpose,r_weight):
    match str(r_purpose):
        case "Indoor Urban Reuse (Toilet flushing, laundry)":
            pt_rw = {"CW": 0,"UASB":0,"SBR":1,"VF":0.25,"AF":0,"RBC":0.75,"ST+SAS":0,"MBR":1}
        case 'Non-Potable Outdoor Urban Reuse (Street washing / Car washing)':
            pt_rw = {"CW": 0.5,"UASB":0.25,"SBR":1,"VF":1,"AF":0.25,"RBC":0.75,"ST+SAS":0.5,"MBR":0.5}
        case "Unrestricted Irrigation":
            pt_rw = {"CW": 1,"UASB":0.25,"SBR":0.75,"VF":1,"AF":0.25,"RBC":0.75,"ST+SAS":0.5,"MBR":1}
            p_nre = {"CW": 0.75,"UASB":0.75,"SBR":0,"VF":0.5,"AF":0.75,"RBC":0.5,"ST+SAS":0.75,"MBR":0}
            p_nre = pd.DataFrame([p_nre],index=["Nut_Removal_Eff"])
            r_weight.update(p_nre)
        case "Restricted Agriculture / Aquaculture":
            pt_rw = {"CW": 0,"UASB":1,"SBR":0.5,"VF":1,"AF":0.25,"RBC":0.5,"ST+SAS":0.25,"MBR":1}
            p_nre = {"CW": 0.75,"UASB":0.75,"SBR":0,"VF":0.5,"AF":0.75,"RBC":0.5,"ST+SAS":0.75,"MBR":0}
            p_nre = pd.DataFrame([p_nre],index=["Nut_Removal_Eff"])
            r_weight.update(p_nre)
        case "Industrial Cooling":
            pt_rw = {"CW": 0,"UASB":0.25,"SBR":0.75,"VF":0,"AF":0.25,"RBC":0.25,"ST+SAS":0,"MBR":1}

    pt_rw = pd.DataFrame([pt_rw],index=["Reuse"])
    r_weight.update(pt_rw)

    return 1

def p_type(pr_type,population,r_weight):
    match str(pr_type):
        case "Housing Unit under Horizontal Property Regime":
            pt_rw = {"CW": 0.25,"UASB":0.75,"SBR":1,"VF":0.75,"AF":1,"RBC":0.5,"ST+SAS":0,"MBR":0}
        case "Residential Property with Lot Autonomy":
            if population < 25:
                pt_rw = {"CW": 0.25,"UASB":0.75,"SBR":0.25,"VF":0.50,"AF":0.75,"RBC":0.5,"ST+SAS":1,"MBR":0}
            else:
                pt_rw = {"CW": 0.75,"UASB":0.25,"SBR":0.75,"VF":0.25,"AF":0.25,"RBC":0.50,"ST+SAS":0.25,"MBR":0.75}
        case "Community Residential Core":
            pt_rw = {"CW": 0.75,"UASB":0.5,"SBR":0.25,"VF":0.75,"AF":0.25,"RBC":0.75,"ST+SAS":0.25,"MBR":0.75}
        case "Large-Scale Urban Development Project":
            pt_rw = {"CW": 0.75,"UASB":0.75,"SBR":0.25,"VF":0,"AF":0.25,"RBC":0.25,"ST+SAS":0,"MBR":0.75}

    pt_rw = pd.DataFrame([pt_rw],index=["Project_size"])
    r_weight.update(pt_rw)

    return 1

def calc_pweight(r_weight, w_econ, w_tech, w_soc):

    pweights = {
        'Economic': w_econ,
        'Technical': w_tech,
        'Social': w_soc
    }
    
    for type in r_weight['Type'].unique():

        columns = r_weight.select_dtypes(include=['number']).columns
        mask = r_weight['Type'] == type
        multiplier = pweights[type]/r_weight['Type'].eq(type).sum()
        r_weight.loc[mask,columns] *= multiplier

    return 1

def pg_ind(contaminants,p_gtrap,r_weight):
    
    for contaminant in contaminants:

        a_ind = []
        current_config = {}

        match contaminant:
            case 'Fats, Oils, and Grease':
                if p_gtrap == False:
                    # Without trap: severe effect over the costs and risks of VF y MBR
                    a_ind = ['O&M_Costs', 'Environmental risk']
                    current_config = {
                        0.60: ['VF', 'MBR'],
                        0.70: ['CW']
                    }
                else:
                    # With trap: the entire system becomes expensive in terms of investment and mantainance
                    a_ind = ['Inv_system', 'O&M_Costs']
                    current_config = {
                        # Solution nature-based: Significant economic effect
                        0.80: ['CW', 'VF'], 
                        # Anaerobic and mechanical systems: Moderate effect
                        0.90: ['UASB', 'AF', 'RBC'], 
                        # High tech: Cheaper trap in comparison with the reactor
                        0.95: ['SBR', 'ST+SAS', 'MBR'] 
                    }

            case 'Coarse Suspended Solids and Non-Biodegradable Material':
                a_ind = ['O&M_Costs', 'Environmental risk']
                current_config = {
                    0.60: ['MBR'], # Maximum alert for membrane braiding
                    0.80: ['SBR', 'UASB', 'AF', 'RBC'], # Moderate alert for pump
                    0.95: ['CW', 'VF'] # Almost immune
                }

            case 'Chlorine and Disinfectants':
                a_ind = ['Org_Removal_Eff', 'Pathogen_Inactivation']
                current_config = {
                    0.60: ['VF', 'CW'],   # Macroorganisms are most vulnerable
                    0.80: ['UASB', 'AF'], # Anaerobic sensitivity
                    0.90: ['MBR', 'SBR', 'RBC', 'ST+SAS'] # Volume resilience
                }

            case 'Detergents and Surfactants':
                a_ind = ['Nut_Removal_Eff', 'Environmental risk']
                current_config = {
                    0.80: ['MBR', 'SBR', 'ST+SAS'], # Problems with foam and phosphorus peaks
                    0.75: ['CW'],                # Phosphorus saturation in the filter medium
                    0.90: ['VF', 'UASB', 'AF']   # Minimum impact from foam
                }
            
        for multiplier, techs in current_config.items():
                existing_techs = [t for t in techs if t in r_weight.columns]
                r_weight.loc[a_ind,existing_techs] *= multiplier
    
    return 1

def legal_weights(tech, macro_tier, r_weight):
    """
    Dynamically assigns a normalized legal compliance capability score (0.00 to 1.00).
    1.00 = Excellent/Easily complied with (Low friction).
    0.00 = Inadequate/Severe barrier (High friction).
    
    Tiers are determined by grid stability and macro-development level.
    """
    # Tier 1: Advanced / High Development (High Enforcement, Low Bureaucracy)
    if macro_tier == 1:
        scores = {"ST+SAS": 1.00, "CW": 0.75, "AF": 0.75, "UASB": 0.50, "SBR": 0.50, "MBR": 0.25, "VF":0.75, "RBC":0.75}
        
    # Tier 2: Transitional / Medium Development (Low Enforcement, High Bureaucracy)
    elif macro_tier == 2:
        # CW is penalized due to land tenure risks; MBR drops due to intense testing/operational liability
        scores = {"ST+SAS": 1.00, "AF": 1.00, "UASB": 0.75, "SBR": 0.50, "CW": 0.25, "MBR": 0.00, "VF":0.50, "RBC":0.50}
        
    # Tier 3: Decentralized / Low Development (Low Enforcement, Low/Informal Bureaucracy)
    elif macro_tier == 3:
        # Low formal barriers, but high-tech systems (MBR/SBR) are penalized due to total absence of regulatory framework
        scores = {"ST+SAS": 1.00, "CW": 1.00, "AF": 1.00, "UASB": 1.00, "SBR": 0.75, "MBR": 0.50, "VF":1.00, "RBC":0.25}
        
    # Fallback/Default case if an invalid tier is passed
    else: 
        scores = {}

    scores = pd.DataFrame([scores],index=["Legal_Complexity"])
    r_weight.update(scores)  
    

def climate_weights(climate_zone,r_weight):
    
    match climate_zone:
        case "Tropical_Warm":
            pt_cl = {
                "MBR": 0.75, "RBC": 0.75, "AF": 1.00, "CW": 1.00,
                "UASB": 1.00, "SBR": 0.75, "VF": 1.00, "ST+SAS": 1.00
            }
            
        case "Arid_SemiArid":
            # CW and VF are slightly reduced due to high evapotranspiration water loss,
            # while subsurface options or compact mechanical options score well for direct reuse.
            pt_cl = {
                "MBR": 0.75, "RBC": 0.75, "AF": 1.00, "CW": 0.50,
                "UASB": 1.00, "SBR": 0.75, "VF": 0.75, "ST+SAS": 1.00
            }
            
        case "Temperate_Cold":
            # Mechanical systems take priority to maintain process kinetics.
            # Anaerobic systems (UASB, AF) require massive volumes or heating, scoring lower.
            pt_cl = {
                "MBR": 1.00, "RBC": 0.75, "AF": 0.50, "CW": 0.50,
                "UASB": 0.25, "SBR": 1.00, "VF": 0.50, "ST+SAS": 0.75
            }
            
        case "Unknown / Out of Bounds" | _:
            # Standard safe fallback value (0.5 neutral baseline) so matrix math doesn't break
            pt_cl = {
                "MBR": 0.50, "RBC": 0.50, "AF": 0.50, "CW": 0.50,
                "UASB": 0.50, "SBR": 0.50, "VF": 0.50, "ST+SAS": 0.50
            }
    
    pt_cl = pd.DataFrame([pt_cl],index=["Climate"])
    r_weight.update(pt_cl)


def tech_uf(av_area,e_population,se_tier,p_type,zone,r_weight):

    a_ind = ['Inv_system','O&M_Costs','Environmental risk','Sludge production', 'Supply_Chain_Risk', 'Population size', 'Population density']
    #CW area required per person
    f_cap = 2
    if av_area < f_cap*e_population:
        r_weight.loc[a_ind,'CW'] *= 0.1
    
    if p_type == "Housing Unit under Horizontal Property Regime":
        r_weight.loc[:,'ST+SAS'] = 0
    
    if se_tier < 2 and not isinstance(se_tier,str):
        r_weight.loc[a_ind,'MBR'] *= 0.1
        r_weight.loc[a_ind,'SBR'] *= 0.1
    
    if zone == 1:
        r_weight.loc[:,'MBR'] *= 0.95
        r_weight.loc[a_ind,'RBC'] *= 0.1
        
    return 1