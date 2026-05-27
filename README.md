🌊 Ocean Pollution Detection System

A CNN-based system to detect ocean oil spills and plastic waste from satellite imagery using deep learning.

🚀 Tech Stack
Python · TensorFlow · Keras · OpenCV · Streamlit · CNN

## 📊 Results
- **92% test accuracy** on 10,000+ Sentinel-2 satellite images
- Real-time inference via Streamlit web app
- Reduces manual inspection effort by ~70%

📁 Project Structure
```text
ocean-pollution-detection/
├── ml_model/          # Trained CNN model
├── analysis/          # Data analysis notebooks
├── screenshots/       # App screenshots
├── static/            # Static assets
├── templates/         # HTML templates
├── app.py             # Streamlit application
└── requirements.txt
```

⚙️ How to Run
```bash
pip install -r requirements.txt
streamlit run app.py
```
