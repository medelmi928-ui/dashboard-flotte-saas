import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import time

# --- 1. CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="SaaS Flotte IoT", layout="wide")

# --- 2. CONNEXION BASE DE DONNÉES ---
engine = create_engine("postgresql://neondb_owner:npg_uEt9dKZQe7WO@ep-polished-star-ab3ajoo4-pooler.eu-west-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require")

# --- 3. SÉLECTION DU VÉHICULE (Barre latérale) ---
try:
    with engine.connect() as conn:
        ids = pd.read_sql("SELECT DISTINCT vehicle_id FROM telemetry", conn)
    selected_id = st.sidebar.selectbox("Véhicule à suivre", ids['vehicle_id']) if not ids.empty else None
except Exception as e:
    st.sidebar.error(f"Erreur de connexion à la BDD : {e}")
    selected_id = None

# --- 4. AFFICHAGE DU DASHBOARD ---
if selected_id:
    # Titre dynamique
    st.title(f"🚚 Dashboard Flotte - Camion {selected_id}")
    
    try:
        with engine.connect() as conn:
            # Récupération des 50 dernières lignes pour avoir un bel historique
            df = pd.read_sql(f"SELECT * FROM telemetry WHERE vehicle_id = {selected_id} ORDER BY timestamp DESC LIMIT 50", conn)
            # Récupération des stats globales
            df_globaux = pd.read_sql("SELECT COUNT(DISTINCT vehicle_id) as total FROM telemetry", conn)

        if not df.empty:
            
            # --- SÉCURISATION DES DONNÉES ---
            df['speed'] = pd.to_numeric(df['speed'], errors='coerce').fillna(0)

            # --- LOGIQUE DE SCORE HYPER RÉACTIF ---
            vitesse_actuelle = round(df['speed'].iloc[0], 2)
            
            # Fenêtre réduite à 3 points (environ 6 secondes) pour la réactivité du score
            df_recent = df.head(3).copy()
            exces_recents = int(len(df_recent[df_recent['speed'] > 100]))
            
            df_recent['diff'] = df_recent['speed'].shift(-1) - df_recent['speed']
            freinages_recents = int(len(df_recent[df_recent['diff'] > 15]))
            
            # Pénalités fortes sur un temps très court
            score = int(max(0, 100 - (exces_recents * 40) - (freinages_recents * 30)))
            
            # Nombre d'excès total (historique sur les 50 points)
            exces_total = int(len(df[df['speed'] > 100]))

            # --- SECTION 1 : INDICATEURS CLÉS ---
            c1, c2, c3 = st.columns(3)
            c1.metric("Vitesse actuelle", f"{vitesse_actuelle} km/h")
            
            # Affichage coloré du score
            if score >= 80:
                c2.success(f"Score Sécurité : {score}/100 🟢")
            elif score >= 50:
                c2.warning(f"Score Sécurité : {score}/100 🟠")
            else:
                c2.error(f"Score Sécurité : {score}/100 🔴 (Alertes!)")

            c3.metric("Nombre d'excès (Historique)", exces_total)

            # --- SECTION 2 : GRAPHIQUE ---
            st.subheader("📈 Évolution de la vitesse")
            # On affiche l'évolution sur les 30 derniers points, remis à l'endroit chronologiquement
            df_plot = df.head(30).sort_values('timestamp') 
            st.line_chart(df_plot.set_index('timestamp')['speed'])

            # --- SECTION 3 : CARTE GPS ---
            st.subheader("📍 Position GPS en temps réel")
            if 'latitude' in df.columns and 'longitude' in df.columns:
                map_data = df[['latitude', 'longitude']].rename(columns={'latitude': 'lat', 'longitude': 'lon'})
                map_data['lat'] = pd.to_numeric(map_data['lat'], errors='coerce')
                map_data['lon'] = pd.to_numeric(map_data['lon'], errors='coerce')
                st.map(map_data.dropna())
            else:
                st.warning("Colonnes 'latitude' et 'longitude' introuvables pour afficher la carte.")

            # --- SECTION 4 : DONNÉES BRUTES ET STATS GLOBALES ---
            st.markdown("---")
            colA, colB = st.columns([2, 1]) # Colonne gauche plus large que la droite
            
            with colA:
                st.subheader("📋 Données brutes récentes")
                st.dataframe(df.head(5)) # Les 5 derniers envois
                
            with colB:
                st.subheader("📊 Flotte Globale")
                st.metric("Total véhicules actifs", int(df_globaux['total'].iloc[0]))
                st.metric("Freinages récents (6s)", freinages_recents)

        else:
            st.info("Aucune donnée disponible pour ce véhicule. En attente du simulateur...")

    except Exception as e:
        st.error(f"Erreur d'exécution : {e}")

    # --- 5. RAFRAÎCHISSEMENT TEMPS RÉEL ---
    time.sleep(2)
    st.rerun()

else:
    st.warning("Veuillez sélectionner un véhicule dans le menu de gauche.")