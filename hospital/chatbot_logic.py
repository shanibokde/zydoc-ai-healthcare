import os
import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

class MedicalChatbot:
    def __init__(self):
        self.base_path = os.path.dirname(os.path.abspath(__file__))
        data_path = os.path.join(self.base_path, 'data')

        self.dataset = pd.read_csv(os.path.join(data_path, 'dataset.csv'))
        self.descriptions = pd.read_csv(os.path.join(data_path, 'symptom_Description.csv'))
        self.precausions = pd.read_csv(os.path.join(data_path, 'symptom_precaution.csv'))

        vector_data = np.load(os.path.join(self.base_path, 'symptom_vectors.npy'), allow_pickle=True).item()
        self.symptom_labels = vector_data['labels']
        self.symptom_vectors = vector_data['matrix']

        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.active_symptoms = [] # This must be kept in sync with the session
        self.possible_diseases = self.dataset.copy()

    def get_symptom_from_text(self, user_text):
        user_vec = self.model.encode([user_text.lower()])
        similarities = cosine_similarity(user_vec, self.symptom_vectors)[0]
        best_match_idx = np.argmax(similarities)
        if similarities[best_match_idx] > 0.45:
            return self.symptom_labels[best_match_idx]
        return None

    def filter_diseases(self, symptom, has_symptom=True):
        if self.possible_diseases.empty:
            return
        
        mask = self.possible_diseases.iloc[:, 1:].apply(
            lambda row: row.astype(str).str.strip().str.contains(symptom).any(), axis=1
        )


        if has_symptom:
            new_df = self.possible_diseases[mask]
        else:
            new_df = self.possible_diseases[~mask]

        if not new_df.empty:
            self.possible_diseases = new_df

    def get_next_question(self):
        # Vectorized stacking and filtering
        symptoms_series = (self.possible_diseases.iloc[:, 1:].stack().str.strip().str.replace(' ', '_'))
        
        # This is the "Shield": It ignores anything in active_symptoms
        remaining = symptoms_series[~symptoms_series.isin(self.active_symptoms)]

        if remaining.empty:
            return None
        
        most_common = remaining.value_counts().idxmax()
        return most_common.replace('_', ' ')
    
    def get_final_diagnosis(self):
        if self.possible_diseases.empty:
            return {
                "disease": "Unknown Condition",
                "description": "The symptoms provided do not match our records.",
                "precautions": ["Consult a doctor."]
            }
    
        disease = self.possible_diseases['Disease'].iloc[0].strip()
        try:
            desc = self.descriptions[self.descriptions['Disease'] == disease]['Description'].values[0]
            pre = self.precausions[self.precausions['Disease'] == disease].iloc[:, 1:].values.flatten().tolist()
        except:
            desc = "No description available."
            pre = []

        return {
            "disease": disease,
            "description": desc,
            "precautions": [p for p in pre if str(p) != 'nan']
        }