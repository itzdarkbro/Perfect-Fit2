import gradio as gr
import pyrebase
import time
import requests
from openai import OpenAI
from dotenv import load_dotenv
import os

import firebase_admin
from firebase_admin import credentials, firestore

# Load Chatgpt API
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Firebase Config
firebaseConfig = {
    "apiKey": "AIzaSyDz6lW987jwakz3wQN8so6-3YdWRqBc3Qk",
    "authDomain": "perfect-fit-319f9.firebaseapp.com",
    "projectId": "perfect-fit-319f9",
    "storageBucket": "perfect-fit-319f9.firebasestorage.app",
    "messagingSenderId": "792717911094",
    "appId": "1:792717911094:web:eaeb6013305b967bfe2497",
    "databaseURL": "https://perfect-fit-319f9-default-rtdb.firebaseio.com/"
}

# Firebase
firebase = pyrebase.initialize_app(firebaseConfig)
auth = firebase.auth()
storage = firebase.storage()
db = firebase.database()

# Firestore
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)
firestore_db = firestore.client()

# User sess
user_session = {}

# GPT Size 
def get_size_recommendation(brand, size, fit_rating, height, weight, gender):
    prompt = f"""
A user tried on a {brand} item in size {size}. They said the fit was "{fit_rating}".
Their height is {height} cm, weight is {weight} kg, and gender is {gender}.
Based on this, what size would you recommend they try next in the same brand?
Respond clearly with only the recommended size and reasoning on the size.
"""
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"❌ GPT Error: {e}"

# Authentication
def login_user(email, password):
    try:
        user = auth.sign_in_with_email_and_password(email, password)
        user_session["user"] = user
        return f"✅ Logged in as {email}"
    except:
        try:
            user = auth.create_user_with_email_and_password(email, password)
            user_session["user"] = user
            return f"✅ Account created for {email}"
        except:
            return "❌ Login/Signup failed. Try again."

# Sub Fit Log
def submit_fit_log(brand, size, fit_rating, height, weight, gender, image_path):
    if "user" not in user_session:
        return "❌ Please log in first."

    user = user_session["user"]
    user_id = user["localId"]
    id_token = user["idToken"]
    timestamp = int(time.time())
    image_filename = f"{user_id}_{timestamp}.jpg"

    try:
        if isinstance(image_path, str) and image_path.strip():
            storage_path = f"fit_photos/{image_filename}"
            storage.child(storage_path).put(image_path, id_token)
            image_url = storage.child(storage_path).get_url(id_token)
        else:
            image_url = ""
    except Exception as e:
        print("Image upload error:", e)
        image_url = ""

    data = {
        "brand": brand,
        "size": size,
        "fit_rating": fit_rating,
        "photo_url": image_url,
        "timestamp": timestamp,
        "height_cm": height,
        "weight_kg": weight,
        "gender": gender
    }

    try:
        db_url = f"{firebaseConfig['databaseURL']}fitLogs/{user_id}.json?auth={id_token}"
        response = requests.post(db_url, json=data)
        if response.status_code == 200:
            return "✅ Fit log saved successfully."
        else:
            return f"❌ Error: {response.status_code} - {response.text}"
    except Exception as e:
        return f"❌ Error saving fit log: {e}"

# View Outfits
def view_my_logs():
    if "user" not in user_session:
        return "❌ Please log in first."

    user = user_session["user"]
    user_id = user["localId"]
    id_token = user["idToken"]

    try:
        db_url = f"{firebaseConfig['databaseURL']}fitLogs/{user_id}.json?auth={id_token}"
        response = requests.get(db_url)
        if response.status_code == 200:
            logs = response.json()
            if not logs:
                return "ℹ️ No logs found."

            html_logs = ""
            for log in logs.values():
                brand = log.get("brand", "N/A")
                size = log.get("size", "N/A")
                rating = log.get("fit_rating", "N/A")
                height = log.get("height_cm", "N/A")
                weight = log.get("weight_kg", "N/A")
                gender = log.get("gender", "N/A")
                photo_url = log.get("photo_url", "")

                image_tag = f'<img src="{photo_url}" width="180" style="margin-bottom:8px;"><br>' if photo_url else ''
                html_logs += f"""
                    <div style="margin-bottom:20px; padding:10px; border-bottom:1px solid #ccc">
                        {image_tag}
                        <strong>Brand:</strong> {brand} |
                        <strong>Size:</strong> {size} |
                        <strong>Fit:</strong> {rating}<br>
                        <strong>Height:</strong> {height} cm |
                        <strong>Weight:</strong> {weight} kg |
                        <strong>Gender:</strong> {gender}
                    </div>
                """

            return html_logs
        else:
            return f"❌ Error: {response.status_code} - {response.text}"
    except Exception as e:
        return f"❌ Error loading logs: {e}"

# Sub resale listing
def submit_resale_listing(brand, size, condition, price, contact_info, image_path):
    if "user" not in user_session:
        return "❌ Please log in first."

    user = user_session["user"]
    user_id = user["localId"]
    timestamp = int(time.time())
    image_url = ""

    try:
        if image_path:
            filename = f"resale_{user_id}_{timestamp}.jpg"
            storage_path = f"resale_photos/{filename}"
            storage.child(storage_path).put(image_path, user["idToken"])
            image_url = storage.child(storage_path).get_url(user["idToken"])
    except Exception as e:
        print("Image upload error:", e)

    listing = {
        "brand": brand,
        "size": size,
        "condition": condition,
        "price": price,
        "contact": contact_info,
        "image_url": image_url,
        "timestamp": timestamp,
        "user_id": user_id
    }

    try:
        firestore_db.collection("resale_listings").add(listing)
        return "✅ Resale item listed!"
    except Exception as e:
        return f"❌ Failed to post resale listing: {e}"

# Resle listings
def browse_resale_listings(search_brand, search_size):
    try:
        query = firestore_db.collection("resale_listings")
        if search_brand:
            query = query.where("brand", "==", search_brand)
        if search_size:
            query = query.where("brand", "==", search_size)
        docs = query.stream()
        listings = ""
        for doc in docs:
            d = doc.to_dict()
            image_tag = f'<img src="{d.get("image_url", "")}" width="180" style="margin-bottom:8px;"><br>' if d.get("image_url") else ''
            listings += f"""
                <div style="margin-bottom:20px; padding:10px; border-bottom:1px solid #ccc">
                    {image_tag}
                    <strong>Brand:</strong> {d['brand']} |
                    <strong>Size:</strong> {d['size']} |
                    <strong>Condition:</strong> {d['condition']}<br>
                    <strong>Price:</strong> ${d['price']} |
                    <strong>Contact:</strong> {d['contact']}
                </div>
            """
        return listings or "🔍 No listings found."
    except Exception as e:
        return f"❌ Error browsing listings: {e}"

# THE Gradio UI 
with gr.Blocks(title="Perfect Fit") as app:
    gr.Markdown("""
    <style>
        body {
            background-color: #f4f6fa;
            font-family: 'Segoe UI', sans-serif;
        }
        h1, h2, h3 {
            color: #1e90ff;
        }
        .gr-button {
            background-color: #1e90ff !important;
            color: white !important;
            border-radius: 6px !important;
            padding: 10px 16px !important;
            border: none !important;
        }
        .gr-button:hover {
            background-color: #e74c3c !important;
        }
        .gr-box, .gr-panel {
            background-color: white !important;
            border-radius: 10px !important;
            padding: 20px !important;
            box-shadow: 0 3px 6px rgba(0, 0, 0, 0.1) !important;
            margin-bottom: 15px !important;
        }
        .gr-textbox input, .gr-dropdown select {
            border-radius: 6px !important;
            border: 1px solid #ccc !important;
            padding: 8px !important;
        }
    </style>

    <h1 style='text-align:center;'>Perfect 👟</h1>
    <p style='text-align:center; font-size:18px; color:#555;'>Your AI-powered outfit assistant</p>
    """)

    with gr.Tab("Login / Signup"):
        gr.Markdown("""
        ### Welcome to Perfect Fit!
        Enter your email and a password **(at least 6 characters)**.
        - If you **already have an account**, you'll be logged in.
        - If you **don’t have an account**, one will be created automatically.
        > Your login session allows you to submit fit logs, post resale items, and more!
        """)
        with gr.Row():
            email = gr.Textbox(label="Email")
            password = gr.Textbox(label="Password (min 6 characters)", type="password")
        login_output = gr.Textbox(label="Status", interactive=False)
        gr.Button("Login or Signup").click(
            login_user, inputs=[email, password], outputs=login_output
        )

    with gr.Tab("Submit Your Outfit"):
        gr.Markdown("""
        ### Log Your Outfits for Future Reference
        Fill in the form below to track how an item fit you.
        - **Brand & Size**: Be specific (e.g. "Nike Air Force 1", "M" or "30W x 32L").
        - **Fit Rating**: Tight, perfect, or oversized?
        - **Height & Weight**: For better AI sizing advice.
        - **Fit Photo**: Upload a photo of how the item fits.(optional)
        """)
        with gr.Row():
            brand = gr.Textbox(label="Item & Brand Name", placeholder="e.g., Nike Air Force 1, Zara Trousers")
            size = gr.Textbox(label="Size")
        fit_rating = gr.Textbox(label="How Did It Fit?", placeholder="e.g., snug in chest, loose in waist, too big overall")
        with gr.Row():
            height = gr.Textbox(label="Height (cm)")
            weight = gr.Textbox(label="Weight (kg)")
            gender = gr.Dropdown(["Male", "Female", "Other"], label="Gender")
        fit_photo = gr.Image(type="filepath", label="Upload Fit Photo")
        fit_submit_output = gr.Textbox(label="Result", interactive=False)
        gr.Button("Submit Your Outfit").click(
            submit_fit_log,
            inputs=[brand, size, fit_rating, height, weight, gender, fit_photo],
            outputs=fit_submit_output
        )

    with gr.Tab("See Your Uploaded Fits"):
        view_output = gr.HTML()
        gr.Button("View My Outfits").click(
            view_my_logs, inputs=[], outputs=view_output
        )

    with gr.Tab("AI Size Recommender"):
        gr.Markdown("""
        ### Get Personalized Size Suggestions
        - Describe how your current size fits.
        - Add height, weight, and gender.
        - The AI will recommend a better size in the **same brand**.
        """)
        with gr.Row():
            rec_brand = gr.Textbox(label="Item & Brand Name", placeholder="e.g., Uniqlo Blank White Tee")
            rec_size = gr.Textbox(label="Current Size You Tried")
        rec_fit = gr.Textbox(label="How Did It Fit?", placeholder="Describe the fit, e.g., tight in shoulders")
        with gr.Row():
            rec_height = gr.Textbox(label="Your Height (in cm)")
            rec_weight = gr.Textbox(label="Your Weight (in kg)")
            rec_gender = gr.Dropdown(["Male", "Female", "Other"], label="Gender")
        rec_output = gr.Textbox(label="AI Recommendation", lines=3, interactive=False)
        gr.Button("Get AI Recommendation").click(
            get_size_recommendation,
            inputs=[rec_brand, rec_size, rec_fit, rec_height, rec_weight, rec_gender],
            outputs=rec_output
        )

    with gr.Tab("Post Resale Item"):
        gr.Markdown("""
        ### List Your Clothing for Resale
        Provide details and an image (optional) to list your item for resale.
        """)
        with gr.Row():
            rs_brand = gr.Textbox(label="Brand")
            rs_size = gr.Textbox(label="Size")
        condition = gr.Textbox(label="Condition (e.g., New, Like New, Used)")
        price = gr.Textbox(label="Price (e.g., $40)")
        contact = gr.Textbox(label="Contact Info")
        item_photo = gr.Image(type="filepath", label="Upload Item Photo")
        resale_output = gr.Textbox(label="Status", interactive=False)
        gr.Button("Post Resale Listing").click(
            submit_resale_listing,
            inputs=[rs_brand, rs_size, condition, price, contact, item_photo],
            outputs=resale_output
        )

    with gr.Tab("Browse Listings"):
        gr.Markdown("""
        ### Explore Items for Resale
        Filter by brand or size, or leave blank to see everything.
        If you are unsure about your size enter the product information into the AI size recommender for an accurate fit.            
        """)
        with gr.Row():
            filter_brand = gr.Textbox(label="Filter by Brand")
            filter_size = gr.Textbox(label="Filter by Size")
        browse_output = gr.HTML(label="Matching Listings")
        gr.Button("Search Listings").click(
            browse_resale_listings,
            inputs=[filter_brand, filter_size],
            outputs=browse_output
        )

app.launch(share=True)
