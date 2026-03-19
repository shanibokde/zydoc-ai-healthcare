import os
import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer

# 1. Setup Paths 
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')

def build_symptom_vectors():
    severity_path = os.path.join(DATA_DIR, 'Symptom-severity.csv')

    if not os.path.exists(severity_path):
        print(f"Error: Could not find {severity_path}. Check your data folder!")
        return
    
    df_severity = pd.read_csv(severity_path)

    # Extract symptoms and clean them for the AI
    # We remove underscores so 'skin_rash' becomes 'skin rash' for better similarity matching
    raw_symptoms = df_severity['Symptom'].unique().tolist()
    clean_symptoms = [s.replace('_', ' ').strip() for s in raw_symptoms]

    print(f"--- Processing {len(clean_symptoms)} symptoms ---")

    # initialize the Model
    model = SentenceTransformer('all-MiniLM-L6-v2')

    # Generate the math(Vectors)
    vectors = model.encode(clean_symptoms)

    # Save as a dictionary so the chatbot knows which math belongs to which word
    vector_data = {
        "labels": raw_symptoms,
        "clean": clean_symptoms,
        "matrix": vectors          # The numerical representation
    }

    save_path = os.path.join(BASE_DIR, 'symptom_vectors.npy')
    np.save(save_path, vector_data)
    print(f"----Success! Generated: {save_path}----")

if __name__ == "__main__":
    build_symptom_vectors()