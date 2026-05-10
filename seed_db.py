import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/laxman_resume')
client = MongoClient(MONGO_URI)
db = client.get_database()

def seed_data():
    # 1. Profile Data
    db.profile.update_one({}, {"$set": {
        "name": "Lakshmi Narayan U",
        "title": "Testing & Validation Engineer",
        "birthday": "10 March 2000",
        "phone": "+91 9611440560",
        "email": "lakhs.48114@gmail.com",
        "city": "Hosur, Tamil Nadu",
        "address": "Belagondapalli, Near Indian Bank, Tamil Nadu - 635109",
        "nationality": "Indian",
        "languages": "English, Tamil, Telugu, Kannada, Hindi",
        "objective": "Highly motivated professional with experience in manufacturing, quality inspection, and internal testing."
    }}, upsert=True)

    # 2. Skills Data
    db.skills.delete_many({})
    db.skills.insert_many([
        {"category": "Technical", "name": "Industrial Automation", "percentage": 90},
        {"category": "Technical", "name": "Testing & Validation", "percentage": 95},
        {"category": "Software", "name": "Web Design (HTML/CSS/JS)", "percentage": 85},
        {"category": "Software", "name": "PLC Programming", "percentage": 80}
    ])

    # 3. Experience Data
    db.experience.delete_many({})
    db.experience.insert_many([
        {
            "company": "Dynaspede Integrated Systems Pvt Ltd",
            "location": "Hosur, Tamil Nadu",
            "role": "On-Roll Engineer (Testing & Validation)",
            "tenure": "Sep 2024 - Present",
            "order": 1,
            "details": [
                "SPM (Special Purpose Machine) testing and validation",
                "Installation and commissioning of Industrial test benches",
                "Gearbox testing and performance validation"
            ]
        },
        {
            "company": "TVS Motor Company",
            "location": "Attibele, Bangalore",
            "role": "Quality Inspector",
            "tenure": "Jan 2021 - Sep 2021",
            "order": 2,
            "details": [
                "Incoming material inspection of fuel tanks and frames",
                "Surface preparation quality checking"
            ]
        }
    ])

    # 4. Achievements
    db.achievements.delete_many({})
    db.achievements.insert_many([
        {"text": "Achieved ±1 bar pressure control accuracy"},
        {"text": "Torque & speed limiting implementation"},
        {"text": "Gearbox synchronizer testing expertise"}
    ])

    print("Database seeded successfully with master resume data!")

if __name__ == "__main__":
    seed_data()
